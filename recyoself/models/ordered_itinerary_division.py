# wish I could do this instead https://github.com/sqlalchemy/sqlalchemy/issues/3189

from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship

from .base import Base

if TYPE_CHECKING:
    from .division import Division
    from .itinerary import Itinerary


class OrderedItineraryDivision(Base, table=True):
    itinerary_id: int = Field(foreign_key="itinerary.id")
    itinerary: "Itinerary" = Relationship(back_populates="_itinerary_divisions")
    division_id: int = Field(foreign_key="division.id")
    division: "Division" = Relationship(back_populates="_itinerary_divisions")
    order: int
