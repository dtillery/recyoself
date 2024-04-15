from typing import TYPE_CHECKING, Optional

import sqlalchemy as sa
from sqlmodel import Field, Relationship

from .base import Base

if TYPE_CHECKING:
    from .facility import Facility
    from .itinerary import PermitItinerary


class Division(Base, table=True):
    name: str
    type: str
    division_id: int = Field(unique=True)
    district: str | None
    is_hidden: bool
    is_active: bool
    permit_id: int = Field(foreign_key="facility.id")
    permit: "Facility" = Relationship(back_populates="divisions")
