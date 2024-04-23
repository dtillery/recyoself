from typing import TYPE_CHECKING, Optional

import sqlalchemy as sa
from sqlmodel import Field, Relationship

from .base import Base, BaseEnum

if TYPE_CHECKING:
    from .campsite import Campsite
    from .division import Division
    from .itinerary import Itinerary
    from .lottery import Lottery
    from .organization import Organization
    from .recreation_area import RecreationArea


class FacilityType(str, BaseEnum):
    activity_pass = "Activity Pass"
    archives = "Archives"
    campground = "Campground"
    cemetary_and_memorial = "Cemetery and Memorial"
    construction_camp = "Construction Camp site"
    facility = "Facility"
    federal = "Federal"
    kiosk = "Kiosk"
    library = "Library"
    museum = "Museum"
    fish_hatchery = "National Fish Hatchery"
    permit = "Permit"
    ticket = "Ticket Facility"
    timed_entry = "Timed Entry"
    tree_permit = "Tree Permit"
    reservation = "Venue Reservations"
    visitor_center = "Visitor Center"

    @property
    def pretty_name(self):
        return self.name.replace("_", " ").title()


class Facility(Base, table=True):
    name: str
    facility_id: str = Field(unique=True)
    type: FacilityType = Field(
        sa_column=sa.Column(sa.Enum(FacilityType, create_constraint=True))
    )
    org_id: int = Field(foreign_key="organization.id")
    org: "Organization" = Relationship(back_populates="facilities")
    rec_area_id: int | None = Field(default=None, foreign_key="recreationarea.id")
    rec_area: Optional["RecreationArea"] | None = Relationship(
        back_populates="facilities"
    )
    itineraries: list["Itinerary"] = Relationship(back_populates="permit")
    divisions: list["Division"] = Relationship(back_populates="permit")
    lotteries: list["Lottery"] = Relationship(back_populates="facility")
    campsites: list["Campsite"] = Relationship(back_populates="facility")
