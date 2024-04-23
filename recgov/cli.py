# TODO: consider refactoring to multiple files
# https://stackoverflow.com/questions/34643620/how-can-i-split-my-click-commands-each-with-a-set-of-sub-commands-into-multipl

import datetime
from datetime import timedelta
from typing import TYPE_CHECKING

import click
import questionary as qu
from sqlmodel import col, or_, select

from . import AUTOCOMPLETE_STYLE
from .db import Session, drop_db, init_db
from .models import Campsite, Facility, FacilityType, Itinerary, Lottery, Organization
from .recreationdotgov import RecreationDotGov
from .ridb import RIDB

if TYPE_CHECKING:
    from .division_availability import DivisionAvailability


@click.group(chain=True)
@click.pass_context
def cli(ctx) -> None:
    ctx.obj = {}


@cli.command()
@click.option(
    "--skip-download",
    type=bool,
    is_flag=True,
    help="Use cached files from a previous run.",
)
@click.pass_context
def init(ctx, skip_download) -> None:
    """Initialize the database and load initial entities from RIDB/Rec.gov."""
    init_db()
    ridb = RIDB()
    if not skip_download:
        click.secho(
            f"Fetching RIDB entities full-export CSVs...", bold=True, underline=True
        )
        ridb.fetch_entities()
    with Session.begin() as session:
        click.secho(f"Loading entities into database...", bold=True, underline=True)
        for organization in ridb.make_organizations():
            session.add(organization)
        session.add(ridb.make_org_157())
        for rec_area in ridb.make_rec_areas(session):
            session.add(rec_area)
        for facility in ridb.make_facilities(session):
            session.add(facility)
        for campsite in ridb.make_campsites(session):
            session.add(campsite)
    ctx.invoke(load_lotteries)


@cli.command()
@click.pass_context
def drop(ctx) -> None:
    """Drop the database."""
    if click.confirm("Do you want to drop the database?", abort=True):
        drop_db()


@cli.command()
@click.argument("permit_id")
def load_divisions(permit_id):
    """Load divisions from rec.gov for a given Permit (Facility) ID"""
    with Session.begin() as session:
        permit_stmt = select(Facility).where(Facility.facility_id == permit_id)
        permit = session.scalars(permit_stmt).first()
        if not permit:
            raise ValueError(f"Could not find permit with ID {permit_id}")

        rdg = RecreationDotGov()
        for division in rdg.make_permit_divisions(permit):
            session.add(division)


@cli.command()
def load_lotteries():
    """Load all currently available lotteries from rec.gov"""
    with Session.begin() as session:
        rdg = RecreationDotGov()
        for lottery in rdg.make_lotteries(session):
            session.add(lottery)


@cli.command()
@click.argument("search_substring", type=str, default="")
def list_lotteries(search_substring: str) -> None:
    """List all Lotteries saved in the database.

    Optionally provide SEARCH_SUBSTRING to filter based on a case-insensitive
    search of the lottery's name and description.
    """
    with Session.begin() as session:
        stmt = select(Lottery)
        if search_substring:
            stmt = stmt.where(
                (col(Lottery.name).icontains(search_substring))
                | (col(Lottery.desc).icontains(search_substring))
            )
        lotteries = session.scalars(stmt).all()
        for l in lotteries:
            open_at = f"{l.open_at.date():%-m/%-d/%y}"
            close_at = f"{l.close_at.date():%-m/%-d/%y}"
            access_start = f"{l.access_start_at.date():%-m/%-d/%y}"
            access_end = f"{l.access_end_at.date():%-m/%-d/%y}"
            click.secho(f"{l.name}: {l.desc}", bold=True, underline=True)
            click.echo(f"UUID: {l.lottery_id}")
            click.echo(f"Facility: {l.facility.name} ({l.facility.facility_id})")
            click.echo(f"Status: {l.status.name.title()}")
            click.echo(f"Open From: {open_at} => {close_at}")
            click.echo(f"Winners Access From: {access_start} => {access_end}")
            click.echo()


@cli.command()
@click.argument("facility_id")
@click.pass_context
def list_campsites(ctx, facility_id: str) -> None:
    """List all campsites associated with a given RIDB Facility ID"""
    with Session.begin() as session:
        facility_stmt = select(Facility).where(Facility.facility_id == facility_id)
        facility = session.scalars(facility_stmt).first()
        if not facility:
            raise ValueError(f"Could not find Facility with ID {facility_id}")

        cs_stmt = (
            select(Campsite)
            .where(Campsite.facility == facility)
            .order_by(Campsite.loop)
        )
        cs_results = session.scalars(cs_stmt)
        click.secho(
            f"Campsites at {facility.name} ({facility.facility_id}):",
            bold=True,
            underline=True,
        )
        for c in cs_results.all():
            group = c.group_site and "Group " or ""
            electric = c.electric and "Electric" or "Non-Electric"
            click.echo(
                f"{c.campsite_id}: {c.name} ({c.loop}), {group}{c.type.pretty_name}, {electric}, {c.use.pretty_name}"
            )


@cli.command()
def list_itineraries() -> None:
    """List all Itineraries, with related permit name and all stops."""
    with Session.begin() as session:
        itineraries = session.scalars(select(Itinerary)).all()
        for i in itineraries:
            click.secho(f"{i.name} ({i.permit.name})", bold=True, underline=True)
            click.echo(f"{i.ordered_divisions_str}")
            click.echo()


@cli.command()
@click.option(
    "-t",
    "--type",
    "ftypes",
    multiple=True,
    type=click.Choice([f.name for f in FacilityType], case_sensitive=False),
)
@click.argument("search_substring", type=str, default="")
def list_facilities(ftypes: tuple[str], search_substring: str) -> None:
    """List all Facilities and relevant information, listed alphabetically by type and name.

    Optionally provide "--type" one or more times to filter by FacilityType(s).

    Optionally provide SEARCH_SUBSTRING to filter based on a case-insensitive
    search of the permit's name.
    """
    with Session.begin() as session:
        stmt = select(Facility).order_by(Facility.type, Facility.name)
        if ftypes:
            stmt = stmt.where(or_(Facility.type == FacilityType[t] for t in ftypes))  # type: ignore
        if search_substring:
            stmt = stmt.where(col(Facility.name).icontains(search_substring))
        permits = session.scalars(stmt).all()
        for p in permits:
            click.secho(
                f"{p.type.pretty_name}: {p.name} ({p.facility_id})",
                bold=True,
                underline=True,
            )
            if p.rec_area:
                click.echo(
                    f"Rec Area: {p.rec_area.name} ({p.rec_area.org_rec_area_id})"
                )
            click.echo(f"Org: {p.org.name} ({p.org.abbr})")
            click.echo()


@cli.command()
@click.argument("permit_id")
@click.argument("new_itinerary_name")
@click.pass_context
def create_itinerary(ctx, permit_id, new_itinerary_name) -> None:
    """Create a new, named itinerary for a given Permit (Facility)."""
    with Session.begin() as session:
        permit = session.scalars(
            select(Facility).where(Facility.facility_id == permit_id)
        ).first()
        if not permit:
            click.echo(click.style(f"No Permit found with ID {permit_id}.", fg="red"))
            return

        if not permit.divisions:
            if click.confirm(f'No divisions found for permit "{permit.name}". Load?'):
                ctx.invoke(load_divisions, permit_id=permit_id)
                session.refresh(permit)

        reservable_divisions = [d for d in permit.divisions if d.is_reservable]
        if not reservable_divisions:
            click.echo("No currently reservable sites found. :(")
            return

        meta_info = {
            "list": "List available choices.",
            "save": "Save the constructed itinerary.",
            "cancel": "Exit without saving itinerary.",
        }
        for d in reservable_divisions:
            meta_info[d.name] = f"{d.type}, {d.district}"

        itinerary, curr_itinerary_str, user_input = None, None, None
        click.secho(
            "Begin typing and make a selection to add it to your itinerary.", bold=True
        )
        click.secho('=> "save" to save itinerary as currently constructed')
        click.secho('=> "cancel" to exit without saving the current itinerary')
        click.secho('=> "list" to list all division autocomplete options')
        while True:
            # qu modifies meta_info inplace, so we need a copy. shallow is fine.
            user_input = qu.autocomplete(
                "Choose a division:",
                choices=list(meta_info.keys()),
                meta_information=meta_info.copy(),
                ignore_case=True,
                match_middle=True,
                style=AUTOCOMPLETE_STYLE,
            ).ask()

            if user_input == "save":
                break
            elif user_input in ("cancel", None):
                ctx.abort()
            elif user_input == "":
                click.echo("Please provide an input.")
                continue
            elif user_input == "list":
                click.echo_via_pager(
                    f"{d.name} ({d.type}, {d.district})\n" for d in reservable_divisions
                )

            matching_divisions = [
                d for d in reservable_divisions if user_input.lower() in d.name.lower()
            ]
            exact_match = [
                d for d in matching_divisions if user_input.lower() == d.name.lower()
            ]

            if not matching_divisions:
                click.echo(
                    f'Could find division match for "{user_input}, please try again.'
                )
            elif len(matching_divisions) > 1 and not exact_match:
                matches_str = "\n".join([f">>> {d.name}" for d in matching_divisions])
                click.echo(
                    f"Found multiple matches for {user_input}:\n{matches_str}\nPlease be more specific."
                )
            else:
                division = exact_match and exact_match[0] or matching_divisions[0]
                click.echo(f"Adding {division.name} to the itinerary.")
                if not itinerary:
                    itinerary = Itinerary(name=new_itinerary_name, permit=permit)
                itinerary.add_division(division)
                session.add(itinerary)
                session.flush()
                click.echo(
                    f"Current itinerary includes:\n{itinerary.ordered_divisions_str}"
                )

        if itinerary is None:
            click.echo("No divisions selected, not saving itinerary.")
        elif not itinerary.divisions:
            click.echo("No divisions added, not creating itinerary.")
        else:
            click.echo(
                f'Saving itinerary "{itinerary.name}" with stops:\n{itinerary.ordered_divisions_str}'
            )
            session.add(itinerary)


def find_availability_date_matches(
    availabilities: list["DivisionAvailability"],
) -> list[list[tuple["DivisionAvailability", datetime.date]]]:
    # TODO: make this not dumb
    num_div_avails = len(availabilities)
    matching_avail_dates = []
    for avail_date in availabilities[0].available_dates():
        date_combos = [
            (availabilities[i], avail_date + timedelta(days=i))
            for i in range(num_div_avails)
        ]
        if all([pair[1] in pair[0].available_dates() for pair in date_combos]):
            matching_avail_dates.append(date_combos)
    return matching_avail_dates


def print_availability_matches(
    avail_matches: list[list[tuple["DivisionAvailability", datetime.date]]]
) -> None:
    for match in avail_matches:
        first_day = f"{match[0][1]:%a, %b %-d}"
        last_day = f"{match[-1][1]:%a, %b %-d}"
        click.secho(f"{first_day} - {last_day}", bold=True)
        click.echo(
            "\n".join([f"{i[1]:%-m/%-d/%y}: {i[0].division.name}" for i in match])
        )


@cli.command()
@click.option(
    "--start-date",
    "-s",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    required=True,
    metavar="<YYYY-MM-DD>",
)
@click.option(
    "--end-date",
    "-e",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    required=True,
    metavar="<YYYY-MM-DD>",
)
@click.option(
    "--reversable",
    "-r",
    type=bool,
    is_flag=True,
    help="Find availabilty for reversed-itinerary.",
)
@click.argument("itinerary_name")
@click.pass_context
def find_itinerary_dates(ctx, start_date, end_date, reversable, itinerary_name) -> None:
    """Find available booking dates for a named itinerary."""
    start_date = start_date.date()
    end_date = end_date.date()
    itinerary = None
    with Session.begin() as session:
        itinerary = session.scalars(
            select(Itinerary).where(Itinerary.name == itinerary_name)
        ).first()
        if not itinerary:
            click.echo(f'No itinerary found with name "{itinerary_name}"')
            return

        lotteries = itinerary.permit.lotteries
        relevant_lottery = None
        if len(lotteries) == 0:
            pass
        elif len(lotteries) == 1:
            relevant_lottery = lotteries[0]
        else:
            choices: list[qu.Choice] = []
            question = f'Select a lottery for "{itinerary.permit.name}":'
            for l in lotteries:
                title = f"{l.name}"
                choices.append(qu.Choice(title, value=l))
            relevant_lottery = qu.select(question, choices=choices).ask()
            if relevant_lottery is None:
                ctx.abort()

        rdg = RecreationDotGov()
        division_availabilities: list[DivisionAvailability] = []
        for division in itinerary.divisions:
            division_availabilities.append(
                rdg.make_availabilities(
                    start_date, end_date, division, relevant_lottery
                )
            )

        avail_matches = find_availability_date_matches(division_availabilities)
        avail_matches_reversed = []
        if reversable:
            avail_matches_reversed = find_availability_date_matches(
                division_availabilities[::-1]
            )

        if not (avail_matches or avail_matches_reversed):
            click.secho(
                "No possible date matches found for itinerary. :(", fg="red", bold=True
            )
        else:
            click.secho(
                f"{len(avail_matches)} date matches found:",
                bold=True,
                underline=True,
                fg="green",
            )
            print_availability_matches(avail_matches)
            if reversable:
                click.secho(
                    f"{len(avail_matches_reversed)} reversed-itinerary date matches found:",
                    bold=True,
                    underline=True,
                    fg="green",
                )
                print_availability_matches(avail_matches_reversed)


if __name__ == "__main__":
    cli()
