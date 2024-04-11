from __future__ import annotations

from enum import Enum

from sqlmodel import Field

from .base import Base


class Organization(Base, table=True):
    name: str
    abbreviation: str
    org_id: int = Field(unique=True)
