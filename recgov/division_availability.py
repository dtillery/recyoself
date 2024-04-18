import datetime
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import Division


@dataclass
class DivisionAvailability:

    division: "Division"
    _availabilities: list["AvailabilityInfo"] = field(default_factory=list, repr=False)

    @property
    def availabilities(self) -> list["AvailabilityInfo"]:
        return sorted(self._availabilities)

    def set_availability(
        self, date: str, total_slots: int, available_slots: int, has_walkup: bool
    ) -> None:
        self._availabilities.append(
            AvailabilityInfo(
                date=date,
                total_slots=total_slots,
                available_slots=available_slots,
                has_walkup=has_walkup,
            )
        )

    def available_dates(self, slots: int = 1) -> list[datetime.date]:
        return [
            ai.date
            for ai in self.availabilities
            if ai.available_slots > 0 and ai.total_slots >= slots
        ]


@dataclass(order=True)
class AvailabilityInfo:

    date: datetime.date | str = field(compare=True)
    total_slots: int = field(compare=False)
    available_slots: int = field(compare=False)
    has_walkup: bool = field(compare=False)

    def __post_init__(self) -> None:
        if self.date and not isinstance(self.date, datetime.date):
            self.date = datetime.datetime.strptime(self.date, "%Y-%m-%d").date()

    def __repr__(self) -> str:
        return f"AvailabilityInfo({self.date:%b %d, %Y}: {self.available_slots}/{self.total_slots})"

    @property
    def available(self) -> bool:
        return self.available_slots > 0
