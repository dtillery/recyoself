from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship

from .base import Base


class EntityChecksum(Base, table=True):
    name: str
    checksum: str
