from datetime import datetime
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..config import now_local
from ..db import get_db
from ..models import STREAMS, Claim, Listing, ListingPhoto, User
from ..photos import MAX_PHOTO_BYTES, sniff_image_type
from ..auth import require_role
from ..services import ClaimError, cancel_claim
from ..templating import templates

router = APIRouter(prefix="/hotel")

TEMP_NOTES = ("hot", "cold", "ambient")


def _back(msg: str = "", error: str = "") -> RedirectResponse:
    key, value = ("error", error) if error else ("msg", msg)
    return RedirectResponse(f"/hotel?{key}={quote_plus(value)}", status_code=303)


def _parse_dt(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M")
    except ValueError:
        return None


@router.get("")
def dashboard(request: Request, msg: str = "", error: str = "", user: User = Depends(require_role("hotel")), db: Session = Depends(get_db)):
    listings = list(
        db.scalars(
            select(Listing)
            .where(Listing.hotel_id == user.id)
            .options(selectinload(Listing.claims).selectinload(Claim.claimer))
            .order_by(Listing.created_at.desc())
        )
    )
    return templates.TemplateResponse(
        request, "hotel.html",
        {"user": user, "listings": listings, "msg": msg, "error": error, "now": now_local(), "form": {}},
    )


@router.post("/listings")
def create_listing(
    title: str = Form(...),
    description: str = Form(""),
    stream: str = Form(...),
    price: str = Form(""),
    quantity: int = Form(...),
    pickup_start: str = Form(...),
    pickup_end: str = Form(...),
    address: str = Form(""),
    safe_until: str = Form(...),
    temp_note: str = Form("ambient"),
    photo: UploadFile | None = File(None),
    user: User = Depends(require_role("hotel")),
    db: Session = Depends(get_db),
):
    title = title.strip()
    if not title:
        return _back(error="Give the listing a title.")
    if stream not in STREAMS:
        return _back(error="Choose a stream.")
    if not 1 <= quantity <= 1000:
        return _back(error="Quantity must be between 1 and 1000 portions.")
    if temp_note not in TEMP_NOTES:
        temp_note = "ambient"

    start, end, safe = _parse_dt(pickup_start), _parse_dt(pickup_end), _parse_dt(safe_until)
    if not (start and end and safe):
        return _back(error="Enter valid pickup and safe-until times.")
    if end <= start:
        return _back(error="Pickup end must be after pickup start.")
    if end <= now_local():
        return _back(error="Pickup window has already ended.")
    if safe < end:
        return _back(error="Safe-until must be at or after the end of the pickup window.")

    photo_bytes, photo_type = None, None
    if photo is not None and photo.filename:
        photo_bytes = photo.file.read(MAX_PHOTO_BYTES + 1)
        if len(photo_bytes) > MAX_PHOTO_BYTES:
            return _back(error="Photo is too large. Use an image under 3 MB.")
        photo_type = sniff_image_type(photo_bytes)
        if photo_type is None:
            return _back(error="Photo must be a JPEG, PNG or WebP image.")

    price_cents: int | None = None
    if stream == "deal":
        try:
            price_cents = int(round(float(price) * 100))
        except ValueError:
            return _back(error="Enter a price for the Rescue Deal.")
        if price_cents <= 0:
            return _back(error="Rescue Deal price must be more than zero. Use a free stream to give food away.")

    listing = Listing(
        hotel_id=user.id, title=title, description=description.strip(), stream=stream,
        price_cents=price_cents, quantity=quantity, remaining=quantity,
        pickup_start=start, pickup_end=end, address=(address.strip() or user.address),
        safe_until=safe, temp_note=temp_note,
    )
    db.add(listing)
    db.flush()
    if photo_bytes:
        db.add(ListingPhoto(listing_id=listing.id, content_type=photo_type, data=photo_bytes))
    db.commit()
    return _back(msg="Listing published.")


def _own_listing(db: Session, user: User, listing_id: int) -> Listing | None:
    listing = db.get(Listing, listing_id)
    return listing if listing and listing.hotel_id == user.id else None


@router.post("/listings/{listing_id}/close")
def close_listing(listing_id: int, user: User = Depends(require_role("hotel")), db: Session = Depends(get_db)):
    listing = _own_listing(db, user, listing_id)
    if not listing:
        return _back(error="Listing not found.")
    listing.status = "closed"
    db.commit()
    return _back(msg="Listing closed. Existing reservations stay valid.")


def _own_claim(db: Session, user: User, claim_id: int) -> Claim | None:
    claim = db.get(Claim, claim_id)
    return claim if claim and claim.listing.hotel_id == user.id else None


@router.post("/claims/{claim_id}/picked-up")
def mark_picked_up(claim_id: int, user: User = Depends(require_role("hotel")), db: Session = Depends(get_db)):
    claim = _own_claim(db, user, claim_id)
    if not claim or claim.status != "reserved":
        return _back(error="That reservation can't be marked as picked up.")
    claim.status = "picked_up"
    db.commit()
    return _back(msg="Marked as picked up.")


@router.post("/claims/{claim_id}/cancel")
def hotel_cancel_claim(claim_id: int, user: User = Depends(require_role("hotel")), db: Session = Depends(get_db)):
    claim = _own_claim(db, user, claim_id)
    if not claim:
        return _back(error="Reservation not found.")
    try:
        cancel_claim(db, claim)
    except ClaimError as e:
        return _back(error=str(e))
    return _back(msg="Reservation cancelled and portions returned.")
