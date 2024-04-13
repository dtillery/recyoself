from typing import Iterator

import requests

from recgov import HEADERS

from .models import Facility, ItineraryStop


class RecreationDotGov:
    base_url: str = "https://www.recreation.gov/api"

    def make_permit_itinerary_stops(self, permit: Facility) -> Iterator[ItineraryStop]:
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
            yield ItineraryStop(**kwargs)

    def _get_divisions(self, permitcontent_id: str) -> dict:
        return self._get(f"permitcontent/{permitcontent_id}/divisions")

    def _get(self, endpoint: str) -> dict:
        url = f"{self.base_url}/{endpoint}"
        r = requests.get(url, headers=HEADERS)
        r.raise_for_status()
        return r.json().get("payload", {})
