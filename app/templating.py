from datetime import datetime
from pathlib import Path

from fastapi.templating import Jinja2Templates

from .models import STREAM_INFO

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def fmt_dt(value: datetime | None) -> str:
    return value.strftime("%a %d %b, %I:%M %p") if value else ""


def fmt_input_dt(value: datetime | None) -> str:
    return value.strftime("%Y-%m-%dT%H:%M") if value else ""


def fmt_price(cents: int | None) -> str:
    if cents is None:
        return "Free"
    rupees = cents / 100
    return f"₹{rupees:,.0f}" if cents % 100 == 0 else f"₹{rupees:,.2f}"


templates.env.filters["dt"] = fmt_dt
templates.env.filters["input_dt"] = fmt_input_dt
templates.env.filters["price"] = fmt_price
templates.env.globals["STREAM_INFO"] = STREAM_INFO
