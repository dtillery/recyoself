from enum import Enum
from typing import TYPE_CHECKING, ClassVar, Optional

from pydantic import ConfigDict
from sqlalchemy.ext.associationproxy import AssociationProxy, association_proxy
from sqlalchemy.ext.orderinglist import ordering_list
from sqlalchemy.orm import relationship
from sqlmodel import Field, Relationship

from .base import Base
from .itinerary_division_link import ItineraryDivisionLink

if TYPE_CHECKING:
    from .division import Division
    from .facility import Facility


class Itinerary(Base, table=True):
    name: str
    permit_id: int = Field(foreign_key="facility.id")
    permit: "Facility" = Relationship(back_populates="itineraries")
    divisions: list["Division"] = Relationship(
        back_populates="itineraries", link_model=ItineraryDivisionLink
    )
    # _divisions = relationship("ItineraryDivisionLink",
    #     back_populates="itinerary", collection_class=ordering_list("order"))
    # divisions: ClassVar = association_proxy("_divisions", "division", creator=lambda div: ItineraryDivisionLink(division=div))

    @property
    def ordered_divisions_str(self) -> str:
        return "\n".join(
            [f"{i}. {d.name}" for i, d in enumerate(self.divisions, start=1)]
        )
