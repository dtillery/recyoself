import datetime
from datetime import datetime as dt
from typing import TYPE_CHECKING, Iterator, Optional

import requests
from sqlmodel import select
from tqdm import tqdm

from recyoself import HEADERS

from .campsite_availability import CampsiteAvailability
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
                if not facility:
                    print(
                        f'Cannot process lottery "{kwargs["name"]} ({kwargs["lottery_id"]}): Facility "{facility_id}" not found.'
                    )
                    continue
                yield Lottery(facility=facility, **kwargs)
                progress_bar.update()

    def make_division_availabilities(
        self,
        start_date: datetime.date,
        end_date: datetime.date,
        division: Division,
        lottery: Optional[Lottery] = None,
    ) -> DivisionAvailability:

        fac_id = division.permit.facility_id
        div_id = division.division_id
        lottery_id = lottery and lottery.lottery_id or None
        in_eap = lottery and lottery.in_early_access or False
        months = list(range(start_date.month, end_date.month + 1))
        year = start_date.year

        div_avail = DivisionAvailability(division)
        for month in months:
            availabilities_by_date = self._get_division_availabilities(
                fac_id, div_id, lottery_id, month, year, in_eap
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

    def make_campsite_availabilities(
        self, start_date: datetime.date, end_date: datetime.date, campground: "Facility"
    ):
        fac_id = campground.facility_id
        months = list(range(start_date.month, end_date.month + 1))
        year = start_date.year
        availabilities: list[CampsiteAvailability] = []

        for month in months:
            for cs_id, cs_data in self._get_campsite_availabilities(
                fac_id, month, year
            ).items():
                cs_avail = CampsiteAvailability(cs_id)
                for date, status in cs_data["availabilities"].items():
                    date = dt.strptime(date, "%Y-%m-%dT%H:%M:%SZ").date()
                    if start_date <= date <= end_date:
                        cs_avail.add_availability(date, status)
                availabilities.append(cs_avail)
        return availabilities

    def _get_divisions(self, permitcontent_id: str) -> dict:
        return self._get(f"permitcontent/{permitcontent_id}/divisions").get(
            "payload", {}
        )

    def _get_lotteries(self) -> list:
        return self._get("lottery/available").get("lotteries", [])

    def _get_division_availabilities(
        self,
        facility_id: str,
        division_id: int,
        lottery_id: Optional["UUID"],
        month: int,
        year: int,
        in_eap: bool = True,
    ) -> dict:

        avail_substr = in_eap and "eapavailability" or "availability"
        url = (
            f"permititinerary/{facility_id}/division/{division_id}/{avail_substr}/month"
        )
        if lottery_id and in_eap:
            url = f"{url}/{lottery_id}"
        params = {"month": month, "year": year}
        quotas = (
            self._get(url, params=params).get("payload", {}).get("quota_type_maps", {})
        )
        # not entirely clear when it's one map type or the other
        # QuotaUsageByMemberDaily also exists for tracking total people
        return quotas.get("QuotaUsageBySiteDaily", {}) or quotas.get(
            "ConstantQuotaUsageDaily", {}
        )

    def _get_campsite_availabilities(
        self, facility_id: str, month: int, year: int
    ) -> dict[str, dict]:
        url = f"camps/availability/campground/{facility_id}/month"
        params = {"start_date": f"{year}-{str(month).zfill(2)}-01T00:00:00.000Z"}
        return self._get(url, params=params).get("campsites", {})

    def _get(self, endpoint: str, params: Optional[dict] = None) -> dict:
        url = f"{self.base_url}/{endpoint}"
        r = requests.get(url, headers=HEADERS, params=params)
        r.raise_for_status()
        return r.json()
