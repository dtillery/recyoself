from typing import TYPE_CHECKING, Optional

import sqlalchemy as sa
from sqlmodel import Field, Relationship

from .base import Base
from .itinerary_division_link import ItineraryDivisionLink

if TYPE_CHECKING:
    from .facility import Facility
    from .itinerary import Itinerary


class Division(Base, table=True):
    name: str
    type: str
    division_id: int = Field(unique=True)
    district: str | None
    is_hidden: bool
    is_active: bool
    permit_id: int = Field(foreign_key="facility.id")
    permit: "Facility" = Relationship(back_populates="divisions")
    itineraries: list["Itinerary"] = Relationship(
        back_populates="divisions", link_model=ItineraryDivisionLink
    )

    def __repr__(self) -> str:
        return f"Division({self.type}: {self.name})"

    @property
    def is_reservable(self):
        return not self.is_hidden and self.is_active
