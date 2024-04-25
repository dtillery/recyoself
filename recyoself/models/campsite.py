from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, Column, Enum
from sqlmodel import Field, Relationship

from .base import Base, BaseEnum

if TYPE_CHECKING:
    from .facility import Facility


class CampsiteType(str, BaseEnum):
    anchorage = "ANCHORAGE"
    ball_field = "BALL FIELD"
    boat_in = "BOAT IN"
    cabin = "CABIN"
    designated_campsite = "Designated Campsite"
    equestrian = "EQUESTRIAN"
    hike_to = "HIKE TO"
    lookout = "LOOKOUT"
    management = "MANAGEMENT"
    mooring = "MOORING"
    overnight_shelter = "OVERNIGHT SHELTER"
    parking = "PARKING"
    picnic = "PICNIC"
    rv = "RV"
    shelter = "SHELTER"
    standard = "STANDARD"
    standard_area = "STANDARD AREA"
    tent_only = "TENT ONLY"
    walk_to = "WALK TO"
    yes = "YES"
    yurt = "YURT"
    zone = "Zone"
    no_type = ""


class UseType(str, BaseEnum):
    overnight = "Overnight"
    day = "Day"
    multi = "multi"


class Campsite(Base, table=True):
    name: str
    loop: str | None = Field(default=None)
    campsite_id: int = Field(sa_column=Column(BigInteger()))
    type: CampsiteType = Field(
        sa_column=Column(Enum(CampsiteType, create_constraint=True))
    )
    electric: bool
    group_site: bool
    use: UseType = Field(sa_column=Column(Enum(UseType, create_constraint=True)))
    facility_id: int = Field(foreign_key="facility.id")
    facility: "Facility" = Relationship(back_populates="campsites")

    @property
    def combined_type(self):
        group = self.group_site and "Group " or ""
        electric = self.electric and "Electric" or "Non-Electric"
        return f"{group}{self.type.pretty_name}, {electric}"
