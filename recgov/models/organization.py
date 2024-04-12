from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship

from .base import Base

if TYPE_CHECKING:
    from .recreation_area import RecreationArea


class Organization(Base, table=True):
    name: str
    abbr: str
    org_id: int = Field(unique=True)
    rec_areas: list["RecreationArea"] = Relationship(back_populates="org")
