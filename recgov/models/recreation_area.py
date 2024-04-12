from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship

from .base import Base

if TYPE_CHECKING:
    from .organization import Organization


class RecreationArea(Base, table=True):
    name: str
    org_rec_area_id: str | None = None
    rec_area_id: int = Field(unique=True)
    org_id: int | None = Field(default=None, foreign_key="organization.id")
    org: "Organization" = Relationship(back_populates="rec_areas")
