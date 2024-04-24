import datetime
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


@dataclass
class CampsiteAvailability:

    campsite_id: str
    _availabilities: list["CampsiteAvailabilityInfo"] = field(
        default_factory=list, repr=False
    )

    @property
    def availabilities(self) -> list["CampsiteAvailabilityInfo"]:
        return sorted(self._availabilities)

    def add_availability(self, date: datetime.date, availability: str) -> None:
        self._availabilities.append(
            CampsiteAvailabilityInfo(date=date, availability=availability)
        )

    def find_reservable_blocks(
        self, days: int, include_nyr: bool = False
    ) -> list[tuple[datetime.date, bool]]:
        dates = [
            a
            for a in self.availabilities
            if a.available or (include_nyr and a.not_yet_reservable)
        ]
        date_ords = [d.date.toordinal() for d in dates]
        num_avail_dates = len(dates)
        leftp = 0
        rightp = days
        starting_dates = []
        while rightp < num_avail_dates:
            ords = date_ords[leftp:rightp]
            all_consecutive = ords == list(range(ords[0], ords[-1] + 1))
            if all_consecutive:
                starting_dates.append((dates[leftp].date, dates[leftp].available))
            leftp += 1
            rightp += 1
        return starting_dates


@dataclass(order=True)
class CampsiteAvailabilityInfo:

    date: datetime.date = field(compare=True)
    availability: str = field(compare=False)

    def __repr__(self) -> str:
        return f"CampsiteAvailabilityInfo({self.date:%b %d, %Y}: {self.availability})"

    @property
    def available(self) -> bool:
        return self.availability == "Available"

    @property
    def reserved(self):
        return self.availability == "Reserved"

    @property
    def not_yet_reservable(self):
        return self.availability == "NYR"

    @property
    def for_management(self):
        return self.availability == "Management"
