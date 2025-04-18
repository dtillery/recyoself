import calendar
import itertools

from rich.console import Console
from rich.table import Table


class AvailabilityCalendar:

    day_abbr: list[str]

    def __init__(self, year: int, firstweekday: int = 6) -> None:
        self.year = year
        self.firstweekday = firstweekday
        calendar.setfirstweekday(self.firstweekday)
        self.day_abbr = calendar.weekheader(3).split()
        self._calendar = calendar.Calendar(self.firstweekday)
        self._console = Console()

        # TODO: not sure if none is correct, probably should just omit inline style
        self.day_styles: dict[int, dict[int, str]] = {
            m: {d: "none" for d in range(1, 32)} for m in range(1, 13)
        }

    @property
    def styled_months(self) -> list[int]:
        styled_months = []
        for m, days in self.day_styles.items():
            for d, style in days.items():
                if style != "none":
                    styled_months.append(m)
                    break
        return styled_months

    def print_month(self, month: int) -> None:
        t = self._calendar_table_base(calendar.month_name[month])
        styled_dates = [
            f"[{self.day_styles[month][d]}]{d}" if d != 0 else ""
            for d in self._calendar.itermonthdays(self.year, month)
        ]
        for week_dates in itertools.batched(styled_dates, 7):
            t.add_row(*week_dates)
        self._console.print(t)

    def _calendar_table_base(self, month_name: str) -> Table:
        t = Table(title=f"{month_name} {self.year}")
        for day in self.day_abbr:
            t.add_column(day, justify="center")
        return t

    def set_available(self, month: int, day: int) -> None:
        self.day_styles[month][day] = "green4 bold"
