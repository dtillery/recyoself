import calendar
import datetime
import os
import tempfile
import time
from datetime import timedelta
from typing import TYPE_CHECKING
from zipfile import ZipFile

import click
import requests
from dotenv import load_dotenv
from sqlmodel import select
from tqdm import tqdm

from .campsite import Campsite, CampsiteAvailability
from .db import Session, drop_db, init_db
from .models import Facility, Itinerary, Organization
from .recreationdotgov import RecreationDotGov
from .ridb import RIDB

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


def get_campsites(permit_area_id) -> list[Campsite]:
    url = f"{RECGOV_PERMIT_CONTENT_URL}/{permit_area_id}"
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()
    data = r.json()

    campsites = []
    divisions = data["payload"]["divisions"]
    for division_id, division_data in divisions.items():
        is_hidden = division_data["is_hidden"]
        if not is_hidden:
            dataclass_args = {
                "campsite_id": division_id,
                "permit_area_id": permit_area_id,
                "district": division_data["district"],
                "full_name": division_data["name"],
                "children": division_data.get("children", []),
            }
            c = Campsite(**dataclass_args)
            campsites.append(c)
    return campsites


def set_availability(
    campsite: Campsite,
    start_date: datetime.date,
    end_date: datetime.date,
    lottery_id: str,
) -> None:
    url = f"{RECGOV_PERMIT_ITINERARY_URL}/{campsite.permit_area_id}/division/{campsite.campsite_id}/eapavailability/month/{lottery_id}"
    months = list(range(start_date.month, end_date.month + 1))
    for month in months:
        print(
            f"Fetching {calendar.month_name[month]} availabilities for {campsite.name}..."
        )
        params = {"month": int(month), "year": 2024}
        r = requests.get(url, params=params, headers=HEADERS)
        r.raise_for_status()
        data = r.json()
        dates = data["payload"]["quota_type_maps"]["QuotaUsageBySiteDaily"]
        for date, date_data in dates.items():
            date = datetime.datetime.strptime(date, "%Y-%m-%d").date()
            if start_date <= date <= end_date:
                campsite.save_availability(date, date_data)
        time.sleep(1)


def find_workable_itineraries(campsites) -> list:
    num_campsites = len(campsites)
    start_campsite = campsites[0]
    workable_itineraries = []
    for date in start_campsite.available_dates():
        itinerary = [
            (campsites[i], date + timedelta(days=i)) for i in range(num_campsites)
        ]
        if all([pair[1] in pair[0].available_dates() for pair in itinerary]):
            workable_itineraries.append(itinerary)
    return workable_itineraries


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
                f'Saving itinerary "{itinerary.name} with stops:\n{itinerary.ordered_divisions_str}'
            )
            session.add(itinerary)


@cli.command()
@click.option("--start", "-s", type=click.DateTime(formats=["%Y-%m-%d"]), required=True)
@click.option("--end", "-e", type=click.DateTime(formats=["%Y-%m-%d"]), required=True)
@click.option("--reversable", "-r", type=bool, is_flag=True)
@click.option("--eap-lottery-id", type=str, envvar="RECGOV_EAP_LOTTERY_ID")
@click.argument("campsites", nargs=-1)
def find_itineraries(start, end, reversable, eap_lottery_id, campsites) -> None:
    start = start.date()
    end = end.date()
    fetched_campsites = {
        c.abbreviation: c
        for c in get_campsites(PERMIT_AREA_ID)
        if c.abbreviation in campsites
    }
    ordered_campsites = [fetched_campsites[abbr] for abbr in campsites]
    if len(ordered_campsites) != len(campsites):
        raise Exception(
            f"Could not fetch all provided campsites ({campsites}), check your abbreviations"
        )

    for campsite in ordered_campsites:
        set_availability(campsite, start, end, eap_lottery_id)

    print(f'=== "{' > '.join(campsites)}" from {start:%m/%d/%Y} to {end:%m/%d/%Y} ===')
    itineraries = find_workable_itineraries(ordered_campsites)

    reversed_itineraries = []
    if reversable:
        reversed_itineraries = find_workable_itineraries(ordered_campsites[::-1])

    if not (itineraries or reversed_itineraries):
        print("No possible matches found for given campsites. :(")
    else:
        print(f"{len(itineraries)} possible matches found:")
        for itinerary in itineraries:
            print(
                " > ".join([f"{i[0].abbreviation} ({i[1]:%b %d})" for i in itinerary])
            )
        if reversable:
            print(f"{len(reversed_itineraries)} possible reversed-matches found:")
            for itinerary in reversed_itineraries:
                print(
                    " > ".join(
                        [f"{i[0].abbreviation} ({i[1]:%b %d})" for i in itinerary]
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
