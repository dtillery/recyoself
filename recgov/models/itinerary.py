from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship

from .base import Base

if TYPE_CHECKING:
    from .facility import Facility


class PermitItinerary(Base, table=True):
    name: str
    permit_id: int = Field(foreign_key="facility.id")
    permit: "Facility" = Relationship(back_populates="itineraries")
