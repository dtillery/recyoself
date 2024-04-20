import datetime
from datetime import datetime as dt
from typing import TYPE_CHECKING, Iterator, Optional

import requests
from sqlmodel import select
from tqdm import tqdm

from recgov import HEADERS

from .division_availability import DivisionAvailability
from .models import Division, Facility, Lottery

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.orm import Session

    from .models import Division


class RecreationDotGov:
    base_url: str = "https://www.recreation.gov/api"

    def make_permit_divisions(self, permit: Facility) -> Iterator[Division]:
        divisions = self._get_divisions(permit.facility_id)
        num_divisions = len(divisions)
        with tqdm(
            total=num_divisions, unit="divs", desc="Loading Divisions"
        ) as progress_bar:
            for division_id, division in divisions.items():
                kwargs = {
                    "name": division["name"],
                    "type": division["type"] or None,
                    "division_id": division_id,
                    "district": division["district"],
                    "permit": permit,
                    "is_hidden": division["is_hidden"],
                    "is_active": division["is_active"],
                }
                yield Division(**kwargs)
                progress_bar.update()

    def make_lotteries(self, session: "Session") -> Iterator[Lottery]:
        lotteries = self._get_lotteries()
        num_lotteries = len(lotteries)
        with tqdm(
            total=num_lotteries, unit="lottos", desc="Loading Lotteries"
        ) as progress_bar:
            for lottery_data in lotteries:
                facility_id = lottery_data["inventory_id"]
                facility_stmt = select(Facility).where(
                    Facility.facility_id == facility_id
                )
                facility = session.scalars(facility_stmt).first()
                kwargs = {
                    "lottery_id": lottery_data["id"],
                    "name": lottery_data["name"],
                    "desc": lottery_data["description"],
                    "summary": lottery_data["summary"],
                    "status": lottery_data["status"],
                    "type": lottery_data["inventory_type"],
                    "display_at": dt.fromisoformat(lottery_data["display_at"]),
                    "open_at": dt.fromisoformat(lottery_data["open_at"]),
                    "close_at": dt.fromisoformat(lottery_data["close_at"]),
                    "scheduled_run_at": dt.fromisoformat(lottery_data["scheduled_at"]),
                    "ran_at": dt.fromisoformat(lottery_data["ran_at"]),
                    "announced_at": dt.fromisoformat(lottery_data["announced_at"]),
                    "access_start_at": dt.fromisoformat(
                        lottery_data["inventory_info"]["dates"]["start"]
                    ),
                    "access_end_at": dt.fromisoformat(
                        lottery_data["inventory_info"]["dates"]["end"]
                    ),
                }
                yield Lottery(facility=facility, **kwargs)
                progress_bar.update()

    def make_availabilities(
        self,
        start_date: datetime.date,
        end_date: datetime.date,
        division: Division,
        lottery: Optional[Lottery] = None,
    ) -> DivisionAvailability:
        fac_id = division.permit.facility_id
        div_id = division.division_id
        lottery_id = lottery and lottery.lottery_id or None
        months = list(range(start_date.month, end_date.month + 1))
        year = start_date.year
        div_avail = DivisionAvailability(division)
        for month in months:
            availabilities_by_date = self._get_availabilities(
                fac_id, div_id, lottery_id, month, year
            )
            for date, avail_data in availabilities_by_date.items():
                date = dt.strptime(date, "%Y-%m-%d").date()
                if start_date <= date <= end_date:
                    div_avail.set_availability(
                        date=date,
                        total_slots=avail_data["total"],
                        available_slots=avail_data["remaining"],
                        has_walkup=avail_data["show_walkup"],
                    )
        return div_avail

    def _get_divisions(self, permitcontent_id: str) -> dict:
        return self._get(f"permitcontent/{permitcontent_id}/divisions")

    def _get_lotteries(self):
        url = f"{self.base_url}/lottery/available"
        r = requests.get(url, headers=HEADERS)
        r.raise_for_status()
        return r.json().get("lotteries", [])

    def _get_availabilities(
        self,
        facility_id: str,
        division_id: int,
        lottery_id: Optional["UUID"],
        month: int,
        year: int,
        eap: bool = True,
    ) -> dict:
        avail_substr = eap and "eapavailability" or "availability"
        url = (
            f"permititinerary/{facility_id}/division/{division_id}/{avail_substr}/month"
        )
        if lottery_id:
            url = f"{url}/{lottery_id}"
        params = {"month": month, "year": year}
        return (
            self._get(url, params=params)
            .get("quota_type_maps", {})
            .get("QuotaUsageBySiteDaily", {})
        )

    def _get(self, endpoint: str, params: Optional[dict] = None) -> dict:
        url = f"{self.base_url}/{endpoint}"
        r = requests.get(url, headers=HEADERS, params=params)
        r.raise_for_status()
        return r.json().get("payload", {})
