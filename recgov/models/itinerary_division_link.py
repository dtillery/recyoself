from typing import TYPE_CHECKING

from sqlmodel import Field

from .base import Base

if TYPE_CHECKING:
    from .division import Division
    from .itinerary import Itinerary


class ItineraryDivisionLink(Base, table=True):
    itinerary_id: int = Field(foreign_key="itinerary.id")
    # itinerary: "Itinerary" = Relationship(back_populates="divisions")
    division_id: int = Field(foreign_key="division.id")
    # division: "Division" = Relationship(back_populates="itineraries")
    # order: int
