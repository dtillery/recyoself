from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlmodel import Field, Relationship

from .base import Base

if TYPE_CHECKING:
    from .facility import Facility


class LotteryStatus(str, Enum):
    active = "LotteryStatusActive"
    executed = "LotteryStatusExecuted"


class LotteryType(str, Enum):
    queue_lottery = "queuelottery"
    camping = "camping"
    ticket = "ticket"
    permit = "permit"


class Lottery(Base, table=True):
    lottery_id: UUID
    name: str
    desc: str | None
    summary: str | None
    status: LotteryStatus
    type: LotteryType
    facility_id: int = Field(foreign_key="facility.id")
    facility: "Facility" = Relationship(back_populates="lotteries")
    display_at: datetime
    open_at: datetime
    close_at: datetime
    scheduled_run_at: datetime
    ran_at: datetime
    announced_at: datetime
    access_start_at: datetime
    access_end_at: datetime
