from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .config import now_local
from .db import Base

ROLES = ("hotel", "customer", "ngo", "shelter", "admin")
CERTIFIED_ROLES = ("ngo", "shelter")
STREAMS = ("deal", "give", "shelter")

# Which stream each claimer role may see and claim.
ROLE_STREAM = {"customer": "deal", "ngo": "give", "shelter": "shelter"}

STREAM_INFO = {
    "deal": {"label": "Rescue Deal", "who": "Customers", "blurb": "Discounted, finish today"},
    "give": {"label": "Community Give", "who": "Certified NGOs", "blurb": "Free, for people in need"},
    "shelter": {"label": "Shelter Feed", "who": "Certified shelters", "blurb": "Free, for animals"},
}


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))
    org_name: Mapped[str] = mapped_column(String(160))
    address: Mapped[str] = mapped_column(String(300), default="")
    # hotel/customer/admin: "verified". ngo/shelter: pending -> verified | rejected
    verification_status: Mapped[str] = mapped_column(String(20), default="verified")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)

    @property
    def is_verified(self) -> bool:
        return self.verification_status == "verified"


class Listing(Base):
    __tablename__ = "listings"

    id: Mapped[int] = mapped_column(primary_key=True)
    hotel_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    stream: Mapped[str] = mapped_column(String(10), index=True)
    price_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quantity: Mapped[int] = mapped_column(Integer)
    remaining: Mapped[int] = mapped_column(Integer)
    pickup_start: Mapped[datetime] = mapped_column(DateTime)
    pickup_end: Mapped[datetime] = mapped_column(DateTime)
    address: Mapped[str] = mapped_column(String(300))
    safe_until: Mapped[datetime] = mapped_column(DateTime)
    temp_note: Mapped[str] = mapped_column(String(20), default="ambient")
    status: Mapped[str] = mapped_column(String(20), default="open")  # open | closed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)

    hotel: Mapped[User] = relationship()
    claims: Mapped[list["Claim"]] = relationship(back_populates="listing")
    # Row only (image bytes are deferred), so `listing.photo` is a cheap "has a photo?" check.
    photo: Mapped["ListingPhoto | None"] = relationship(uselist=False, lazy="selectin")

    @property
    def is_free(self) -> bool:
        return self.stream in ("give", "shelter")

    @property
    def display_status(self) -> str:
        now = now_local()
        if self.status == "closed":
            return "closed"
        if self.pickup_end <= now or self.safe_until <= now:
            return "expired"
        if self.remaining <= 0:
            return "fully claimed"
        return "open"


class ListingPhoto(Base):
    __tablename__ = "listing_photos"

    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"), primary_key=True)
    content_type: Mapped[str] = mapped_column(String(40))
    data: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"), index=True)
    claimer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    qty: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="reserved")  # reserved | picked_up | cancelled
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)

    listing: Mapped[Listing] = relationship(back_populates="claims")
    claimer: Mapped[User] = relationship()
