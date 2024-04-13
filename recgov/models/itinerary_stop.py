from typing import TYPE_CHECKING, Optional

from aenum import MultiValueEnum
from sqlmodel import Field, Relationship

from .base import Base

if TYPE_CHECKING:
    from .facility import Facility
    from .itinerary import PermitItinerary


class ItineraryStopType(MultiValueEnum):
    zone = "Zone"
    campsite = "Campsite", "Camp Area", "Trailside Camps"


class ItineraryStop(Base, table=True):
    name: str
    type: ItineraryStopType
    division_id: int
    district: str | None
    is_hidden: bool
    is_active: bool
    permit_id: int = Field(foreign_key="facility.id")
    permit: "Facility" = Relationship(back_populates="stops")
