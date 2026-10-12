from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..auth import require_role
from ..db import get_db
from ..models import Claim, Listing, User
from ..services import ClaimError, can_claim, cancel_claim, claim_listing, open_listings_for, stream_for
from ..templating import templates

router = APIRouter(prefix="/browse")


def _back(msg: str = "", error: str = "") -> RedirectResponse:
    key, value = ("error", error) if error else ("msg", msg)
    return RedirectResponse(f"/browse?{key}={quote_plus(value)}", status_code=303)


@router.get("")
def browse(
    request: Request,
    q: str = "",
    msg: str = "",
    error: str = "",
    user: User = Depends(require_role("customer", "ngo", "shelter")),
    db: Session = Depends(get_db),
):
    listings = open_listings_for(db, user, q)
    claims = list(
        db.scalars(
            select(Claim)
            .where(Claim.claimer_id == user.id)
            .options(selectinload(Claim.listing).selectinload(Listing.hotel))
            .order_by(Claim.created_at.desc())
        )
    )
    return templates.TemplateResponse(
        request, "browse.html",
        {
            "user": user, "listings": listings, "claims": claims, "q": q, "msg": msg, "error": error,
            "allowed": can_claim(user), "stream": stream_for(user),
        },
    )


@router.post("/claim/{listing_id}")
def claim(
    listing_id: int,
    qty: int = Form(1),
    user: User = Depends(require_role("customer", "ngo", "shelter")),
    db: Session = Depends(get_db),
):
    try:
        claim_listing(db, user, listing_id, qty)
    except ClaimError as e:
        return _back(error=str(e))
    return _back(msg="Reserved. Pick it up in the window shown below.")


@router.post("/claims/{claim_id}/cancel")
def cancel(
    claim_id: int,
    user: User = Depends(require_role("customer", "ngo", "shelter")),
    db: Session = Depends(get_db),
):
    c = db.get(Claim, claim_id)
    if not c or c.claimer_id != user.id:
        return _back(error="Reservation not found.")
    try:
        cancel_claim(db, c)
    except ClaimError as e:
        return _back(error=str(e))
    return _back(msg="Reservation cancelled.")
