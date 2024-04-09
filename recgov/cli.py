import calendar
import datetime
import time
from datetime import timedelta

import click
import requests
from dotenv import load_dotenv

from .campsite import Campsite, CampsiteAvailability

load_dotenv()

PERMIT_AREA_ID = 4675321  # Glacier National Park

RECGOV_BASE_URL = "https://www.recreation.gov/api"
RECGOV_PERMIT_CONTENT_URL = f"{RECGOV_BASE_URL}/permitcontent"
RECGOV_PERMIT_ITINERARY_URL = f"{RECGOV_BASE_URL}/permititinerary"

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15"
HEADERS = {"user-agent": USER_AGENT}


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


@click.group()
@click.pass_context
def cli(ctx):
    ctx.obj = {}


@cli.command()
@click.option("--start", "-s", type=click.DateTime(formats=["%Y-%m-%d"]), required=True)
@click.option("--end", "-e", type=click.DateTime(formats=["%Y-%m-%d"]), required=True)
@click.option("--reversable", "-r", type=bool, is_flag=True)
@click.option("--eap-lottery-id", type=str, envvar="RECGOV_EAP_LOTTERY_ID")
@click.argument("campsites", nargs=-1)
def find_itineraries(start, end, reversable, eap_lottery_id, campsites):
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


if __name__ == "__main__":
    cli()
