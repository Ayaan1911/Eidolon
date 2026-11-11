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


import pytest  # noqa: E402


def _jpeg_with_gps(lat, lat_ref, lon, lon_ref) -> bytes:
    exif = Image.Exif()
    table = exif.get_ifd(GPS_IFD)
    table[1], table[2], table[3], table[4] = lat_ref, lat, lon_ref, lon
    out = BytesIO()
    Image.new("RGB", (2, 2)).save(out, "JPEG", exif=exif)
    return out.getvalue()


@pytest.mark.parametrize(
    "lat,lat_ref,lon,lon_ref",
    [
        ((91.0, 0.0, 0.0), "N", (10.0, 0.0, 0.0), "E"),  # latitude out of range
        ((10.0, 0.0, 0.0), "N", (181.0, 0.0, 0.0), "E"),  # longitude out of range
        ((10.0, 60.0, 0.0), "N", (10.0, 0.0, 0.0), "E"),  # minutes out of range
        ((10.0, 0.0, 0.0), "E", (10.0, 0.0, 0.0), "E"),  # a latitude cannot be east
        ((10.0, 0.0, 0.0), "N", (10.0, 0.0, 0.0), "S"),  # a longitude cannot be south
        ((10.0, 0.0, 0.0), "X", (10.0, 0.0, 0.0), "E"),  # not a hemisphere at all
    ],
)
def test_invalid_gps_is_not_reported_as_a_location(client, lat, lat_ref, lon, lon_ref):
    r = upload(client, _jpeg_with_gps(lat, lat_ref, lon, lon_ref))
    assert r.status_code == 200
    body = r.json()
    assert body["has_location"] is False and body["latitude"] is None and body["longitude"] is None


def test_valid_gps_at_the_edges_is_kept(client):
    body = upload(client, _jpeg_with_gps((90.0, 0.0, 0.0), "S", (180.0, 0.0, 0.0), "W")).json()
    assert (body["latitude"], body["longitude"]) == (-90.0, -180.0)


def test_a_truncated_image_is_a_clean_400(client):
    assert upload(client, make_jpeg(gps=True)[:60]).status_code == 400


def test_the_server_reads_only_one_byte_past_the_limit(client, monkeypatch):
    from starlette.datastructures import UploadFile

    asked = []
    real_read = UploadFile.read

    async def spy(self, size=-1):
        asked.append(size)
        return await real_read(self, size)

    monkeypatch.setattr(UploadFile, "read", spy)
    assert upload(client, b"\0" * (MAX_PHOTO_BYTES + 5)).status_code == 413
    assert asked == [MAX_PHOTO_BYTES + 1]


@pytest.mark.parametrize("dms", [(float("nan"), 0, 0), (float("inf"), 0, 0), (-5.0, 0, 0), (1, 2), ("a", 0, 0), None])
def test_non_finite_negative_or_malformed_dms_is_rejected(dms):
    from services.photo_metadata import _dms_to_decimal

    assert _dms_to_decimal(dms, "N", "lat") is None
