# TODO: consider refactoring to multiple files
# https://stackoverflow.com/questions/34643620/how-can-i-split-my-click-commands-each-with-a-set-of-sub-commands-into-multipl

import datetime
import os
import pkgutil
from datetime import timedelta
from pathlib import Path
from string import Template
from typing import TYPE_CHECKING, Optional

import click
import questionary as qu
from rich_click import RichCommand, RichGroup
from sqlmodel import col, or_, select

from . import AUTOCOMPLETE_STYLE
from .db import Session, drop_db, init_db
from .models import (
    Campsite,
    Facility,
    FacilityType,
    Itinerary,
    Lottery,
    LotteryStatus,
    LotteryType,
    Organization,
)
from .recreationdotgov import RecreationDotGov
from .ridb import RIDB

if TYPE_CHECKING:
    from .division_availability import DivisionAvailability

DAEMON_MODE: bool = False


@click.group(cls=RichGroup, chain=True)
@click.pass_context
def cli(ctx) -> None:
    ctx.obj = {}


def echo(message: str = "", override: bool = False, **kwargs):
    if not DAEMON_MODE or override:
        click.secho(message, **kwargs)


@cli.command(cls=RichCommand)
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
        echo(f"Fetching RIDB entities full-export CSVs...", bold=True, underline=True)
        ridb.fetch_entities()
    with Session.begin() as session:
        echo(f"Loading entities into database...", bold=True, underline=True)
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


@cli.command(cls=RichCommand)
@click.pass_context
def drop(ctx) -> None:
    """Drop the database."""
    if click.confirm("Do you want to drop the database?", abort=True):
        drop_db()


@cli.command(cls=RichCommand)
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


@cli.command(cls=RichCommand)
def load_lotteries():
    """Load all currently available lotteries from rec.gov"""
    with Session.begin() as session:
        rdg = RecreationDotGov()
        for lottery in rdg.make_lotteries(session):
            session.add(lottery)


@cli.command(cls=RichCommand)
@click.option(
    "-t",
    "--type",
    "ltypes",
    multiple=True,
    type=click.Choice([t.name for t in LotteryType], case_sensitive=False),
)
@click.option(
    "-s",
    "--status",
    "statuses",
    multiple=True,
    type=click.Choice([s.name for s in LotteryStatus], case_sensitive=False),
)
@click.option(
    "--order",
    "order_by",
    type=click.Choice(["open"], case_sensitive=False),
)
@click.argument("search_substring", type=str, default="")
def list_lotteries(
    ltypes: tuple[str],
    statuses: tuple[str],
    order_by: str | None,
    search_substring: str,
) -> None:
    """List all Lotteries saved in the database.

    Optionally provide SEARCH_SUBSTRING to filter based on a case-insensitive
    search of the lottery's name and description.
    """
    with Session.begin() as session:
        stmt = select(Lottery)
        if ltypes:
            stmt = stmt.where(or_(Lottery.type == LotteryType[t] for t in ltypes))  # type: ignore
        if statuses:
            stmt = stmt.where(or_(Lottery.status == LotteryStatus[s] for s in statuses))  # type: ignore
        if order_by == "open":
            stmt = stmt.order_by(col(Lottery.open_at).asc())
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
            echo(f"{l.name}: {l.desc}", bold=True, underline=True)
            echo(f"Type: {l.type.name.title()}")
            echo(f"UUID: {l.lottery_id}")
            echo(f"Facility: {l.facility.name} ({l.facility.facility_id})")
            echo(f"Status: {l.status.name.title()}")
            echo(f"Open From: {open_at} => {close_at}")
            echo(f"Winners Access From: {access_start} => {access_end}")
            echo()


@cli.command(cls=RichCommand)
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
        echo(
            f"Campsites at {facility.name} ({facility.facility_id}):",
            bold=True,
            underline=True,
        )
        for c in cs_results.all():
            group = c.group_site and "Group " or ""
            electric = c.electric and "Electric" or "Non-Electric"
            echo(
                f"{c.campsite_id}: {c.name} ({c.loop}), {c.combined_type}, {c.use.pretty_name}"
            )


@cli.command(cls=RichCommand)
def list_itineraries() -> None:
    """List all Itineraries, with related permit name and all stops."""
    with Session.begin() as session:
        itineraries = session.scalars(select(Itinerary)).all()
        for i in itineraries:
            echo(f"{i.name} ({i.permit.name})", bold=True, underline=True)
            echo(f"{i.ordered_divisions_str}")
            echo()


@cli.command(cls=RichCommand)
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
            echo(
                f"{p.type.pretty_name}: {p.name} ({p.facility_id})",
                bold=True,
                underline=True,
            )
            if p.rec_area:
                echo(f"Rec Area: {p.rec_area.name} ({p.rec_area.org_rec_area_id})")
            echo(f"Org: {p.org.name} ({p.org.abbr})")
            echo()


@cli.command(cls=RichCommand)
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
            echo(click.style(f"No Permit found with ID {permit_id}.", fg="red"))
            return

        if not permit.divisions:
            if click.confirm(f'No divisions found for permit "{permit.name}". Load?'):
                ctx.invoke(load_divisions, permit_id=permit_id)
                session.refresh(permit)

        reservable_divisions = [d for d in permit.divisions if d.is_reservable]
        if not reservable_divisions:
            echo("No currently reservable sites found. :(")
            return

        meta_info = {
            "list": "List available choices.",
            "save": "Save the constructed itinerary.",
            "cancel": "Exit without saving itinerary.",
        }
        for d in reservable_divisions:
            meta_info[d.name] = f"{d.type}, {d.district}"

        itinerary, curr_itinerary_str, user_input = None, None, None
        echo(
            "Begin typing and make a selection to add it to your itinerary.", bold=True
        )
        echo('=> "save" to save itinerary as currently constructed')
        echo('=> "cancel" to exit without saving the current itinerary')
        echo('=> "list" to list all division autocomplete options')
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
                echo("Please provide an input.")
                continue
            elif user_input == "list":
                echo_via_pager(
                    f"{d.name} ({d.type}, {d.district})\n" for d in reservable_divisions
                )

            matching_divisions = [
                d for d in reservable_divisions if user_input.lower() in d.name.lower()
            ]
            exact_match = [
                d for d in matching_divisions if user_input.lower() == d.name.lower()
            ]

            if not matching_divisions:
                echo(f'Could find division match for "{user_input}, please try again.')
            elif len(matching_divisions) > 1 and not exact_match:
                matches_str = "\n".join([f">>> {d.name}" for d in matching_divisions])
                echo(
                    f"Found multiple matches for {user_input}:\n{matches_str}\nPlease be more specific."
                )
            else:
                division = exact_match and exact_match[0] or matching_divisions[0]
                echo(f"Adding {division.name} to the itinerary.")
                if not itinerary:
                    itinerary = Itinerary(name=new_itinerary_name, permit=permit)
                itinerary.add_division(division)
                session.add(itinerary)
                session.flush()
                echo(f"Current itinerary includes:\n{itinerary.ordered_divisions_str}")

        if itinerary is None:
            echo("No divisions selected, not saving itinerary.")
        elif not itinerary.divisions:
            echo("No divisions added, not creating itinerary.")
        else:
            echo(
                f'Saving itinerary "{itinerary.name}" with stops:\n{itinerary.ordered_divisions_str}'
            )
            session.add(itinerary)


def find_division_availability_date_matches(
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
        echo(f"{first_day} - {last_day}", override=True, bold=True)
        echo(
            "\n".join([f"{i[1]:%-m/%-d/%y}: {i[0].division.name}" for i in match]),
            override=True,
        )


@cli.command(cls=RichCommand)
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
    default=None,
    metavar="<YYYY-MM-DD>",
)
@click.option(
    "--reversable",
    "-r",
    type=bool,
    is_flag=True,
    help="Find availabilty for reversed-itinerary.",
)
@click.option(
    "--lottery-id",
    "-l",
    type=str,
    help="rec.gov Lottery ID to use (and skips prompt)",
    default=None,
)
@click.option(
    "--daemon-mode",
    type=bool,
    is_flag=True,
    help="Output only if availabilities are found (for daemonizing purposes)",
)
@click.argument("itinerary_name")
@click.pass_context
def find_itinerary_dates(
    ctx,
    start_date: datetime.datetime,
    end_date: Optional[datetime.datetime],
    reversable: bool,
    lottery_id: Optional[str],
    daemon_mode: bool,
    itinerary_name: str,
) -> None:
    """Find available booking dates for a named itinerary."""
    global DAEMON_MODE
    DAEMON_MODE = daemon_mode
    start = start_date.date()
    end = end_date and end_date.date() or start
    itinerary = None
    with Session.begin() as session:
        itinerary = session.scalars(
            select(Itinerary).where(Itinerary.name == itinerary_name)
        ).first()
        if not itinerary:
            echo(f'No itinerary found with name "{itinerary_name}"')
            return

        lotteries = itinerary.permit.lotteries
        relevant_lottery = None
        if len(lotteries) == 0:
            pass
        elif len(lotteries) == 1:
            relevant_lottery = lotteries[0]
        else:
            if lottery_id:
                for l in lotteries:
                    if str(l.lottery_id).lower() == lottery_id.lower():
                        relevant_lottery = l
                        break
                if relevant_lottery is None:
                    raise ValueError(f"Could not find lottery with id: {lottery_id}")
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
                rdg.make_division_availabilities(start, end, division, relevant_lottery)
            )

        avail_matches = find_division_availability_date_matches(division_availabilities)
        avail_matches_reversed = []
        if reversable:
            avail_matches_reversed = find_division_availability_date_matches(
                division_availabilities[::-1]
            )

        if not (avail_matches or avail_matches_reversed):
            echo(
                "No possible date matches found for itinerary. :(", fg="red", bold=True
            )
        else:
            echo(
                f"{len(avail_matches)} date matches found:",
                override=True,
                bold=True,
                underline=True,
                fg="green",
            )
            print_availability_matches(avail_matches)
            if reversable:
                echo(
                    f"{len(avail_matches_reversed)} reversed-itinerary date matches found:",
                    override=True,
                    bold=True,
                    underline=True,
                    fg="green",
                )
                print_availability_matches(avail_matches_reversed)


@cli.command(cls=RichCommand)
@click.option(
    "--start-date",
    "-s",
    "start",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    required=True,
    metavar="<YYYY-MM-DD>",
)
@click.option(
    "--end-date",
    "-e",
    "end",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    metavar="<YYYY-MM-DD>",
)
@click.option(
    "--include-nyr",
    "nyr",
    type=bool,
    is_flag=True,
    help="Include sites and dates that are Not Yet Reservable",
)
@click.option(
    "--daemon-mode",
    type=bool,
    is_flag=True,
    help="Output only if availabilities are found (for daemonizing purposes)",
)
@click.argument("campground_id", type=str)
@click.argument("num_days", type=int)
@click.pass_context
def find_campsite_dates(
    ctx,
    start: datetime.datetime,
    end: Optional[datetime.datetime],
    nyr: bool,
    daemon_mode: bool,
    campground_id: str,
    num_days: int,
) -> None:
    """Find available reservation dates a campground."""
    global DAEMON_MODE
    DAEMON_MODE = daemon_mode
    start_date = start.date()
    end_date = end and end.date() or start.date()
    end_of_trip_date = end_date + timedelta(days=num_days)

    with Session.begin() as session:
        stmt = select(Facility).where(Facility.facility_id == campground_id)
        campground = session.scalars(stmt).first()
        if not campground:
            raise ValueError(
                f"Could not find Campground (Facility) with ID {campground_id}"
            )

        rdg = RecreationDotGov()
        reservable_block_list: list[tuple[Campsite, tuple]] = []
        for ca in rdg.make_campsite_availabilities(
            start_date, end_of_trip_date, campground
        ):
            reservable_blocks = ca.find_reservable_blocks(num_days, include_nyr=nyr)
            if reservable_blocks:
                cs = session.scalars(
                    select(Campsite).where(Campsite.campsite_id == ca.campsite_id)
                ).first()
                if cs:
                    reservable_block_list.append((cs, reservable_blocks))

        if not reservable_block_list:
            echo("No open campsites found. :(", fg="red", bold=True)
        else:
            echo(
                f"{campground.name}: {num_days}-day availabilities from {start_date:%b %-d} to {end_date:%b %-d}",
                override=True,
                bold=True,
                underline=True,
            )
            for cs, blocks in reservable_block_list:
                echo(
                    f"Site {cs.name} ({cs.loop}): {cs.combined_type}, starting on:",
                    override=True,
                    bold=True,
                )
                for date, curr_avail in blocks:
                    s = f"{date:%a, %b %-d}"
                    color = "green"
                    if not curr_avail:
                        s += " (NYR)"
                        color = "yellow"
                    echo(s, override=True, fg=color)


@cli.command(cls=RichCommand)
@click.option("--name", type=str, required=True)
@click.option("--interval", type=int, required=True, default=900, show_default=True)
@click.option("--workdir", type=click.Path(exists=True), default=lambda: Path.home())
@click.option("--logdir", type=click.Path(), required=True)
@click.option(
    "--env-path",
    type=str,
    default="/bin:/usr/bin:/usr/local/bin:~/.local/bin",
    show_default=True,
)
@click.option("--env-cmd", type=str, default="recyoself", show_default=True)
@click.option("--env-cmd-args", type=str, default="")
@click.option("--env-notify-name", type=str, required=True)
@click.option("--env-email", type=str, required=True)
@click.option("--script-path", type=click.Path(), default=None)
@click.argument("output_dir", type=click.Path())
def make_launchd_configs(
    name: str,
    interval: int,
    workdir: str,
    logdir: str,
    env_path: str,
    env_cmd: str,
    env_cmd_args: str,
    env_notify_name: str,
    env_email: str,
    script_path: Optional[str],
    output_dir: str,
) -> None:
    if not script_path:
        script_path = os.path.join(output_dir, "run-and-alert.sh")
    daemon_name = f"com.recyoself.daemon.{name}.plist"
    substitutions = {
        "daemon_name": daemon_name,
        "daemon_interval": interval,
        "daemon_workdir": workdir,
        "daemon_logdir": logdir,
        "daemon_env_path": env_path,
        "daemon_env_cmd": env_cmd,
        "daemon_env_cmd_args": env_cmd_args,
        "daemon_env_notify_name": env_notify_name,
        "daemon_env_email": env_email,
        "daemon_script_path": script_path,
    }

    plist_template_path = (
        "templates/daemon/launchd/com.recyoself.daemon.cmd.plist.template"
    )
    plist_data = Template(pkgutil.get_data(__name__, plist_template_path).decode())  # type: ignore
    plist_text = plist_data.substitute(substitutions)

    plist_output_path = os.path.join(output_dir, daemon_name)
    with open(plist_output_path, "w") as f:
        f.write(plist_text)

    script_data = pkgutil.get_data(__name__, "templates/daemon/run-and-alert.sh").decode()  # type: ignore
    with open(script_path, "w") as f:
        f.write(script_data)
    os.chmod(script_path, 0o744)


if __name__ == "__main__":
    cli()
