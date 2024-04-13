from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship

from .base import Base

if TYPE_CHECKING:
    from .itinerary import PermitItinerary
    from .itinerary_stop import ItineraryStop
    from .organization import Organization
    from .recreation_area import RecreationArea


class FacilityType(str, Enum):
    activity_pass = "Activity Pass"
    archives = "Archives"
    campground = "Campground"
    cemetary_and_memorial = "Cemetary and Memorial"
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
    type: FacilityType
    org_id: int = Field(foreign_key="organization.id")
    org: "Organization" = Relationship(back_populates="facilities")
    rec_area_id: int | None = Field(default=None, foreign_key="recreationarea.id")
    rec_area: Optional["RecreationArea"] | None = Relationship(
        back_populates="facilities"
    )
    itineraries: list["PermitItinerary"] = Relationship(back_populates="permit")
    stops: list["ItineraryStop"] = Relationship(back_populates="permit")
