import datetime
from dataclasses import dataclass, field


@dataclass
class Campsite:

    campsite_id: int
    permit_area_id: int
    district: str
    full_name: str
    children: list[str] = field(repr=False)
    _availabilities: list["CampsiteAvailability"] = field(
        default_factory=list, repr=False
    )

    @property
    def name(self) -> str:
        parts = self.full_name.split()
        index_of_hyphen = parts.index("-")
        return " ".join(parts[index_of_hyphen + 1 :])

    @property
    def abbreviation(self) -> str:
        parts = self.full_name.split()
        index_of_hyphen = parts.index("-")
        return parts[index_of_hyphen - 1]

    def save_availability(self, date: str, date_data: dict) -> None:
        kwargs = {
            "date": date,
            "total_sites": date_data["total"],
            "available_sites": date_data["remaining"],
            "has_walkup": date_data["show_walkup"],
        }
        self._availabilities.append(CampsiteAvailability(**kwargs))

    @property
    def availabilities(self) -> list["CampsiteAvailability"]:
        return sorted(self._availabilities)

    def available_dates(self, sites: int = 1) -> list[datetime.date]:
        return [
            ca.date
            for ca in self.availabilities
            if ca.available_sites > 0 and ca.total_sites >= sites
        ]


@dataclass(order=True)
class CampsiteAvailability:

    date: datetime.date = field(compare=True)
    total_sites: int = field(compare=False)
    available_sites: int = field(compare=False)
    has_walkup: bool = field(compare=False)

    def __post_init__(self) -> None:
        if self.date and not isinstance(self.date, datetime.date):
            self.date = datetime.datetime.strptime(self.date, "%Y-%m-%d").date()

    def __repr__(self) -> str:
        return f"CampsiteAvailability({self.date:%b %d, %Y}: {self.available_sites}/{self.total_sites})"

    @property
    def available(self) -> bool:
        return self.available_sites > 0
