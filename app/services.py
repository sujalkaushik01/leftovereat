"""Business rules for listings and claims."""
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .config import now_local
from .models import ROLE_STREAM, Claim, Listing, User


class ClaimError(Exception):
    pass


def stream_for(user: User) -> str | None:
    return ROLE_STREAM.get(user.role)


def can_claim(user: User) -> bool:
    """Customers always; NGO/shelter only once an admin has verified them."""
    stream = stream_for(user)
    if stream is None:
        return False
    if user.role in ("ngo", "shelter"):
        return user.is_verified
    return True


def open_listings_for(db: Session, user: User, q: str = "") -> list[Listing]:
    if not can_claim(user):
        return []
    now = now_local()
    stmt = (
        select(Listing)
        .where(
            Listing.stream == stream_for(user),
            Listing.status == "open",
            Listing.remaining > 0,
            Listing.pickup_end > now,
            Listing.safe_until > now,
        )
        .order_by(Listing.pickup_end)
    )
    rows = list(db.scalars(stmt))
    q = q.strip().lower()
    if q:
        rows = [
            r for r in rows
            if q in r.title.lower() or q in r.address.lower() or q in r.hotel.org_name.lower()
        ]
    return rows


def claim_listing(db: Session, user: User, listing_id: int, qty: int) -> Claim:
    if not can_claim(user):
        raise ClaimError("Your account can't claim food yet.")
    if qty < 1:
        raise ClaimError("Choose at least one portion.")
    listing = db.get(Listing, listing_id)
    if listing is None or listing.stream != stream_for(user):
        raise ClaimError("That listing isn't available to your account.")

    now = now_local()
    # Atomic decrement: only succeeds if enough stock remains and the listing is still live.
    result = db.execute(
        update(Listing)
        .where(
            Listing.id == listing_id,
            Listing.status == "open",
            Listing.remaining >= qty,
            Listing.pickup_end > now,
            Listing.safe_until > now,
        )
        .values(remaining=Listing.remaining - qty)
    )
    if result.rowcount != 1:
        db.rollback()
        raise ClaimError("Not enough portions left, or the pickup window has closed.")
    claim = Claim(listing_id=listing_id, claimer_id=user.id, qty=qty, status="reserved")
    db.add(claim)
    db.commit()
    return claim


def cancel_claim(db: Session, claim: Claim) -> None:
    if claim.status != "reserved":
        raise ClaimError("Only reserved claims can be cancelled.")
    claim.status = "cancelled"
    db.execute(
        update(Listing).where(Listing.id == claim.listing_id).values(remaining=Listing.remaining + claim.qty)
    )
    db.commit()


def meals_reserved(db: Session) -> int:
    from sqlalchemy import func

    total = db.scalar(select(func.coalesce(func.sum(Claim.qty), 0)).where(Claim.status != "cancelled"))
    return int(total or 0)
