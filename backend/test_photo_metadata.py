"""Photo EXIF extraction. Images are generated in memory with Pillow - no real photos.

Run from backend/:  python -m pytest test_photo_metadata.py
"""

from io import BytesIO

from PIL import Image

from routers.exposure import MAX_PHOTO_BYTES

GPS_IFD, EXIF_IFD = 0x8825, 0x8769  # EXIF sub-table ids, same constants the service uses


def make_jpeg(*, gps=False, device=False, taken=False) -> bytes:
    """A 2x2 JPEG carrying only the EXIF fields asked for."""
    exif = Image.Exif()
    if device:
        exif[0x010F] = "TestMake"
        exif[0x0110] = "TestModel"
    if taken:
        exif.get_ifd(EXIF_IFD)[0x9003] = "2024:05:06 07:08:09"
    if gps:
        table = exif.get_ifd(GPS_IFD)
        table[1], table[2] = "N", (37.0, 25.0, 19.0)  # 37 deg 25 min 19 sec north
        table[3], table[4] = "W", (122.0, 5.0, 0.0)  # 122 deg 5 min west
    out = BytesIO()
    Image.new("RGB", (2, 2)).save(out, "JPEG", exif=exif)
    return out.getvalue()


def upload(client, data: bytes, name="photo.jpg"):
    return client.post("/api/exposure/photo", files={"file": (name, data, "image/jpeg")})


def test_photo_with_gps_is_flagged_and_decoded(client):
    body = upload(client, make_jpeg(gps=True, device=True, taken=True)).json()
    assert body["has_location"] is True
    assert body["latitude"] == 37 + 25 / 60 + 19 / 3600  # north is positive
    assert body["longitude"] == -(122 + 5 / 60)  # west is negative
    assert body["device"] == "TestMake TestModel"
    assert body["captured_at"] == "2024:05:06 07:08:09"


def test_photo_without_exif_has_no_location(client):
    body = upload(client, make_jpeg()).json()
    assert body == {"has_location": False, "latitude": None, "longitude": None, "device": None, "captured_at": None}


def test_photo_with_exif_but_no_gps_is_not_flagged(client):
    body = upload(client, make_jpeg(device=True, taken=True)).json()
    assert body["has_location"] is False
    assert body["latitude"] is None and body["longitude"] is None
    assert body["device"] == "TestMake TestModel"  # other metadata is still reported


def test_non_image_upload_is_rejected(client):
    r = upload(client, b"this is plain text, not an image", name="notes.jpg")
    assert r.status_code == 400
    assert r.json()["detail"] == "Could not read this file as an image"


def test_oversized_upload_is_rejected(client):
    assert upload(client, b"\0" * (MAX_PHOTO_BYTES + 1)).status_code == 413


def test_upload_exactly_at_the_limit_is_not_rejected_for_size(client):
    # Zeros are not an image, so this must fail as 400 (unreadable), not 413 (too big).
    assert upload(client, b"\0" * MAX_PHOTO_BYTES).status_code == 400
