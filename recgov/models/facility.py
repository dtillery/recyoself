from enum import Enum
from typing import TYPE_CHECKING, Optional

import sqlalchemy as sa
from sqlmodel import Field, Relationship

from .base import Base

if TYPE_CHECKING:
    from .division import Division
    from .itinerary import PermitItinerary
    from .organization import Organization
    from .recreation_area import RecreationArea


class FacilityType(str, Enum):
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
    itineraries: list["PermitItinerary"] = Relationship(back_populates="permit")
    divisions: list["Division"] = Relationship(back_populates="permit")
