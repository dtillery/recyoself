from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlmodel import Field, Relationship

from .base import Base, BaseEnum

if TYPE_CHECKING:
    from .facility import Facility


class LotteryStatus(str, BaseEnum):
    active = "LotteryStatusActive"
    executed = "LotteryStatusExecuted"


class LotteryType(str, BaseEnum):
    queue_lottery = "queuelottery"
    camping = "camping"
    ticket = "ticket"
    permit = "permit"


class Lottery(Base, table=True):
    lottery_id: UUID = Field(index=True)
    name: str = Field(index=True)
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

    @property
    def in_early_access(self):
        return self.access_start_at < datetime.now() < self.access_end_at
