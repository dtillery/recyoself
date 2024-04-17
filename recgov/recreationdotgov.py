from datetime import datetime as dt
from typing import TYPE_CHECKING, Iterator

import requests
from sqlmodel import select

from recgov import HEADERS

from .models import Division, Facility, Lottery

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class RecreationDotGov:
    base_url: str = "https://www.recreation.gov/api"

    def make_permit_divisions(self, permit: Facility) -> Iterator[Division]:
        for division_id, division in self._get_divisions(permit.facility_id).items():
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

    def make_lotteries(self, session: "Session") -> Iterator[Lottery]:
        for lottery_data in self._get_lotteries():
            facility_id = lottery_data["inventory_id"]
            facility_stmt = select(Facility).where(Facility.facility_id == facility_id)
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

    def _get_divisions(self, permitcontent_id: str) -> dict:
        return self._get(f"permitcontent/{permitcontent_id}/divisions")

    def _get_lotteries(self):
        url = f"{self.base_url}/lottery/available"
        r = requests.get(url, headers=HEADERS)
        r.raise_for_status()
        return r.json().get("lotteries", [])

    def _get(self, endpoint: str) -> dict:
        url = f"{self.base_url}/{endpoint}"
        r = requests.get(url, headers=HEADERS)
        r.raise_for_status()
        return r.json().get("payload", {})
