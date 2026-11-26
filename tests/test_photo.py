from datetime import timedelta

from app.config import now_local
from tests.test_flow import dt, register

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def listing_form():
    return {
        "title": "Photo food", "description": "", "stream": "deal", "price": "40", "quantity": 3,
        "pickup_start": dt(-1), "pickup_end": dt(3), "safe_until": dt(4), "temp_note": "hot", "address": "",
    }


def test_photo_upload_and_serve(client_factory):
    hotel, cust = client_factory(), client_factory()
    register(hotel, "hotel", "h@t.test", "Hotel A")
    register(cust, "customer", "c@t.test", "Cust")
    r = hotel.post("/hotel/listings", data=listing_form(), files={"photo": ("a.png", PNG, "image/png")})
    assert "msg=" in r.headers["location"], r.headers["location"]
    page = cust.get("/browse").text
    assert "/photos/1" in page
    img = cust.get("/photos/1")
    assert img.status_code == 200 and img.headers["content-type"] == "image/png" and img.content == PNG


def test_non_image_rejected(client_factory):
    hotel = client_factory()
    register(hotel, "hotel", "h@t.test", "Hotel A")
    r = hotel.post("/hotel/listings", data=listing_form(), files={"photo": ("a.png", b"not an image", "image/png")})
    assert "error=" in r.headers["location"]
    assert hotel.get("/photos/1").status_code == 404


def test_listing_without_photo_still_works(client_factory):
    hotel = client_factory()
    register(hotel, "hotel", "h@t.test", "Hotel A")
    r = hotel.post("/hotel/listings", data=listing_form())
    assert "msg=" in r.headers["location"]
    assert hotel.get("/photos/1").status_code == 404
