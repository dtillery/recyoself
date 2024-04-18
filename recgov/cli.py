import calendar
import datetime
import os
import tempfile
import time
from datetime import timedelta
from typing import TYPE_CHECKING
from zipfile import ZipFile

import click
import questionary as qu
import requests
from dotenv import load_dotenv
from sqlmodel import select
from tqdm import tqdm

from .db import Session, drop_db, init_db
from .models import Facility, Itinerary, Organization
from .recreationdotgov import RecreationDotGov
from .ridb import RIDB

if TYPE_CHECKING:
    from .division_availability import DivisionAvailability

load_dotenv()

BASE_DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data"))

PERMIT_AREA_ID: int = 4675321  # Glacier National Park

RECGOV_BASE_URL: str = "https://www.recreation.gov/api"
RECGOV_PERMIT_CONTENT_URL: str = f"{RECGOV_BASE_URL}/permitcontent"
RECGOV_PERMIT_ITINERARY_URL: str = f"{RECGOV_BASE_URL}/permititinerary"

RIDB_FULL_CSV_URL: str = (
    "https://ridb.recreation.gov/downloads/RIDBFullExport_V1_CSV.zip"
)
RIDB_ENTITIES: list[str] = ["Campsites", "Facilities", "Organizations", "RecAreas"]

USER_AGENT: str = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15"
)
HEADERS: dict = {"user-agent": USER_AGENT}


@click.group(chain=True)
@click.pass_context
def cli(ctx) -> None:
    ctx.obj = {}


@cli.command()
@click.option("--skip-download", type=bool, is_flag=True)
def init(skip_download) -> None:
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
    drop_db()


@cli.command()
@click.argument("permit_id")
def load_divisions(permit_id):
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
    with Session.begin() as session:
        rdg = RecreationDotGov()
        for lottery in rdg.make_lotteries(session):
            session.add(lottery)


@cli.command()
def list_itineraries() -> None:
    with Session.begin() as session:
        itineraries = session.scalars(select(Itinerary)).all()
        for itinerary in itineraries:
            click.echo(f"=== {itinerary.name}")
            click.echo(itinerary.ordered_divisions_str)


@cli.command()
@click.argument("permit_id")
@click.argument("new_itinerary_name")
def create_itinerary(permit_id, new_itinerary_name) -> None:
    with Session.begin() as session:
        permit = session.scalars(
            select(Facility).where(Facility.facility_id == permit_id)
        ).first()
        if not permit:
            click.echo(click.style(f"No Permit found with ID {permit_id}.", fg="red"))
            return

        reservable_divisions = [d for d in permit.divisions if d.is_reservable]
        click.echo(f"Divisions available for {permit.name}:")
        for division in reservable_divisions:
            click.echo(f'({division.type}) "{division.name}"')

        itinerary = Itinerary(name=new_itinerary_name, permit=permit)
        curr_itinerary_str, user_input = None, None
        while True:
            user_input = click.prompt(
                'Enter a stop (partial) name ("save" to save, "cancel" to exit)'
            )
            if user_input in ["save", "cancel"]:
                break
            matching_divisions = [
                d for d in reservable_divisions if user_input in d.name.lower()
            ]
            if not matching_divisions:
                click.echo(
                    f'Could find division match for "{user_input}, please try again.'
                )
            elif len(matching_divisions) > 1:
                matches_str = "\n".join([f">>> {d.name}" for d in matching_divisions])
                click.echo(
                    f"Found multiple matches for {user_input}:\n{matches_str}\nPlease be more specific."
                )
            else:
                division = matching_divisions[0]
                click.echo(f"Adding {division.name} to the itinerary.")
                itinerary.divisions.append(division)
                session.add(itinerary)
                session.flush()
            click.echo(
                f"Current itinerary includes:\n{itinerary.ordered_divisions_str}"
            )

        if not itinerary.divisions:
            click.echo("No divisions added, not creating itinerary.")
        elif user_input == "cancel":
            click.echo("Not saving itinerary.")
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
@click.option("--start", "-s", type=click.DateTime(formats=["%Y-%m-%d"]), required=True)
@click.option("--end", "-e", type=click.DateTime(formats=["%Y-%m-%d"]), required=True)
@click.option("--reversable", "-r", type=bool, is_flag=True)
@click.option("--eap-lottery-id", type=str, envvar="RECGOV_EAP_LOTTERY_ID")
@click.argument("itinerary_name")
def find_itineray_dates(start, end, reversable, eap_lottery_id, itinerary_name) -> None:
    start = start.date()
    end = end.date()
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
            # TODO: handle appropriately
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
                rdg.make_availabilities(start, end, division, relevant_lottery)
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


@cli.command()
def get_lotteries() -> None:
    lotteries_url = f"{RECGOV_BASE_URL}/lottery/available"
    r = requests.get(lotteries_url, headers=HEADERS)
    r.raise_for_status()

    statuses = set()
    inventory_types = set()

    for lottery in r.json()["lotteries"]:
        inventory_id = lottery["inventory_id"]
        inventory_type = lottery["inventory_type"]
        name = lottery["name"]
        facility_name = lottery["inventory_info"]["facility_name"]
        statuses.add(lottery["status"])
        inventory_types.add(lottery["inventory_type"])
        if inventory_type == "queuelottery":
            print(f"queuelottery: {inventory_id} {name} {facility_name}")

    print(f"Statuses: {statuses}")
    print(f"Inventory Types: {inventory_types}")


if __name__ == "__main__":
    cli()
