from io import BytesIO

from PIL import ExifTags, Image

from models.schemas import PhotoMetadataResponse

# Sub-IFD pointer tags in the main EXIF table; stable IDs across the EXIF spec.
_EXIF_IFD_TAG = 0x8769
_GPS_IFD_TAG = 0x8825
_DATE_TIME_ORIGINAL_TAG = 0x9003


def _dms_to_decimal(dms: tuple, ref: str) -> float:
    degrees, minutes, seconds = (float(v) for v in dms)
    decimal = degrees + minutes / 60 + seconds / 3600
    return -decimal if ref in ("S", "W") else decimal


def extract_photo_metadata(image_bytes: bytes) -> PhotoMetadataResponse:
    image = Image.open(BytesIO(image_bytes))
    exif = image.getexif()

    if not exif:
        return PhotoMetadataResponse(has_location=False)

    tags = {ExifTags.TAGS.get(tag_id, tag_id): value for tag_id, value in exif.items()}

    device_parts = [tags.get("Make"), tags.get("Model")]
    device = " ".join(p.strip() for p in device_parts if isinstance(p, str) and p.strip()) or None

    exif_ifd = exif.get_ifd(_EXIF_IFD_TAG)
    captured_at = exif_ifd.get(_DATE_TIME_ORIGINAL_TAG) or tags.get("DateTime")
    captured_at = str(captured_at) if captured_at else None

    latitude = longitude = None
    gps_ifd = exif.get_ifd(_GPS_IFD_TAG)
    if gps_ifd:
        gps = {ExifTags.GPSTAGS.get(tag_id, tag_id): value for tag_id, value in gps_ifd.items()}
        lat_dms, lat_ref = gps.get("GPSLatitude"), gps.get("GPSLatitudeRef")
        lon_dms, lon_ref = gps.get("GPSLongitude"), gps.get("GPSLongitudeRef")
        if lat_dms and lon_dms and lat_ref and lon_ref:
            latitude = _dms_to_decimal(lat_dms, lat_ref)
            longitude = _dms_to_decimal(lon_dms, lon_ref)

    return PhotoMetadataResponse(
        has_location=latitude is not None,
        latitude=latitude,
        longitude=longitude,
        device=device,
        captured_at=captured_at,
    )
