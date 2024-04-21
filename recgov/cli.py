# TODO: consider refactoring to multiple files
# https://stackoverflow.com/questions/34643620/how-can-i-split-my-click-commands-each-with-a-set-of-sub-commands-into-multipl

import datetime
from datetime import timedelta
from typing import TYPE_CHECKING

import click
import questionary as qu
from dotenv import load_dotenv
from prompt_toolkit.styles import Style
from sqlmodel import col, select

from .db import Session, drop_db, init_db
from .models import Facility, FacilityType, Itinerary, Lottery, Organization
from .recreationdotgov import RecreationDotGov
from .ridb import RIDB

if TYPE_CHECKING:
    from .division_availability import DivisionAvailability

load_dotenv()

# stolen from https://github.com/tmbo/questionary/blob/master/examples/autocomplete_ants.py
AUTOCOMPLETE_STYLE = Style(
    [
        ("separator", "fg:#cc5454"),
        ("qmark", "fg:#673ab7 bold"),
        ("question", ""),
        ("selected", "fg:#cc5454"),
        ("pointer", "fg:#673ab7 bold"),
        ("highlighted", "fg:#673ab7 bold"),
        ("answer", "fg:#f44336 bold"),
        ("text", "fg:#FBE9E7"),
        ("disabled", "fg:#858585 italic"),
    ]
)


@click.group(chain=True)
@click.pass_context
def cli(ctx) -> None:
    ctx.obj = {}


@cli.command()
@click.option("--skip-download", type=bool, is_flag=True)
def init(skip_download) -> None:
    """Initialize the database and load initial entities from RIDB."""
    init_db()
    ridb = RIDB()
    if not skip_download:
        print(f"=== Fetching RIDB entities full-export CSVs...")
        ridb.fetch_entities()
    with Session.begin() as session:
        print(f"=== Loading entities into database...")
        for organization in ridb.make_organizations():
            session.add(organization)
        session.add(ridb.make_org_157())
        for rec_area in ridb.make_rec_areas(session):
            session.add(rec_area)
        for facility in ridb.make_facilities(session):
            session.add(facility)


@cli.command()
def drop() -> None:
    """Drop the database."""
    if click.confirm("Do you want to drop the database?"):
        drop_db()


@cli.command()
@click.argument("permit_id")
def load_divisions(permit_id):
    """Load divisions from rec.gov for a given Permit (Facility) ID"""
    with Session.begin() as session:
        permit_stmt = select(Facility).where(Facility.facility_id == permit_id)
        permit = session.scalars(permit_stmt).first()
        if not permit:
            raise Exception(f"Could not find permit with ID {permit_id}")

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
@click.argument("search_string", type=str, default="")
def list_lotteries(search_string: str) -> None:
    """List all Lotteries saved in the database.

    Optionally provide SEARCH_STRING to filter based on a case-insensitive
    search of the lottery's name and description.
    """
    with Session.begin() as session:
        stmt = select(Lottery)
        if search_string:
            stmt = stmt.where(
                (col(Lottery.name).icontains(search_string))
                | (col(Lottery.desc).icontains(search_string))
            )
        lotteries = session.scalars(stmt).all()
        for l in lotteries:
            click.echo(f"=== {l.name}: {l.desc}")
            click.echo(f"{l.lottery_id}")
            click.echo(f"Facility: {l.facility.name} ({l.facility.facility_id})")
            click.echo(f"Status: {l.status.name}")
            click.echo(f"Open: {l.open_at.date()} - {l.close_at.date()}")
            click.echo(f"Access: {l.access_start_at.date()} - {l.access_end_at.date()}")
            click.echo()


@cli.command()
def list_itineraries() -> None:
    """List all Itineraries, with related permit name and all stops."""
    with Session.begin() as session:
        itineraries = session.scalars(select(Itinerary)).all()
        for i in itineraries:
            click.echo(f"=== {i.name} ({i.permit.name})")
            click.echo(f"{i.ordered_divisions_str}")
            click.echo()


@cli.command()
@click.argument("search_string", type=str, default="")
def list_permits(search_string: str) -> None:
    """List all Facilities that are of the permit type.

    Optionally provide SEARCH_STRING to filter based on a case-insensitive
    search of the permit's name.
    """
    with Session.begin() as session:
        stmt = select(Facility).where(Facility.type == FacilityType.permit)
        if search_string:
            stmt = stmt.where(col(Facility.name).icontains(search_string))
        permits = session.scalars(stmt).all()
        for p in permits:
            click.echo(f"{p.facility_id}: {p.name}")


@cli.command()
@click.argument("permit_id")
@click.argument("new_itinerary_name")
def create_itinerary(permit_id, new_itinerary_name) -> None:
    """Create a new, named itinerary for a given Permit (Facility)."""
    with Session.begin() as session:
        permit = session.scalars(
            select(Facility).where(Facility.facility_id == permit_id)
        ).first()
        if not permit:
            click.echo(click.style(f"No Permit found with ID {permit_id}.", fg="red"))
            return

        reservable_divisions = [d for d in permit.divisions if d.is_reservable]
        if not reservable_divisions:
            click.echo("No reservable sites found. Did you run load-divisions?")
            return

        choices = []
        meta_info = {}
        for d in reservable_divisions:
            choices.append(d.name)
            meta_info[d.name] = f"{d.type}, {d.district}"

        itinerary, curr_itinerary_str, user_input = None, None, None
        while True:
            user_input = qu.autocomplete(
                'Begin typing and make selection to add to your itinerary ("save" to save, "cancel" to cancel)\n',
                choices=choices,
                meta_information=meta_info,
                ignore_case=True,
                match_middle=True,
                style=AUTOCOMPLETE_STYLE,
            ).ask()

            if user_input in ["save", "cancel", None]:
                break

            matching_divisions = [
                d for d in reservable_divisions if user_input.lower() in d.name.lower()
            ]
            exact_match = [
                d for d in matching_divisions if user_input.lower() == d.name.lower()
            ]
            print(matching_divisions)
            print(exact_match)

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

        if user_input is None or user_input == "cancel" or itinerary is None:
            click.echo("Not saving itinerary.")
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
def find_itineray_dates(start_date, end_date, reversable, itinerary_name) -> None:
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
            click.echo("No possible matches found for given campsites. :(")
        else:
            click.echo(f"{len(avail_matches)} possible matches found:")
            for match in avail_matches:
                click.echo(
                    " > ".join([f"{i[0].division.name} ({i[1]:%b %d})" for i in match])
                )
            if reversable:
                click.echo(
                    f"{len(avail_matches_reversed)} possible reversed-matches found:"
                )
                for match in avail_matches_reversed:
                    click.echo(
                        " > ".join(
                            [f"{i[0].division.name} ({i[1]:%b %d})" for i in match]
                        )
                    )


if __name__ == "__main__":
    cli()
