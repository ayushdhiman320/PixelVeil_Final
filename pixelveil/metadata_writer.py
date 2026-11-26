"""EXIF binary encoder and JPEG metadata writer using piexif."""

import os
import shutil
import uuid
import piexif
from .config import OUTPUT_FOLDER

FIELD_TO_TAG = {
    # IFD0 (Image)
    "Make": ("0th", piexif.ImageIFD.Make),
    "Model": ("0th", piexif.ImageIFD.Model),
    "Software": ("0th", piexif.ImageIFD.Software),
    "DateTime": ("0th", piexif.ImageIFD.DateTime),
    "Artist": ("0th", piexif.ImageIFD.Artist),
    "Copyright": ("0th", piexif.ImageIFD.Copyright),
    "Orientation": ("0th", piexif.ImageIFD.Orientation),
    "XResolution": ("0th", piexif.ImageIFD.XResolution),
    "YResolution": ("0th", piexif.ImageIFD.YResolution),
    "ResolutionUnit": ("0th", piexif.ImageIFD.ResolutionUnit),
    "YCbCrPositioning": ("0th", piexif.ImageIFD.YCbCrPositioning),
    # EXIF IFD
    "ExposureTime": ("Exif", piexif.ExifIFD.ExposureTime),
    "FNumber": ("Exif", piexif.ExifIFD.FNumber),
    "ExposureProgram": ("Exif", piexif.ExifIFD.ExposureProgram),
    "ISOSpeedRatings": ("Exif", piexif.ExifIFD.ISOSpeedRatings),
    "ExifVersion": ("Exif", piexif.ExifIFD.ExifVersion),
    "DateTimeOriginal": ("Exif", piexif.ExifIFD.DateTimeOriginal),
    "DateTimeDigitized": ("Exif", piexif.ExifIFD.DateTimeDigitized),
    "ShutterSpeedValue": ("Exif", piexif.ExifIFD.ShutterSpeedValue),
    "ApertureValue": ("Exif", piexif.ExifIFD.ApertureValue),
    "ExposureBiasValue": ("Exif", piexif.ExifIFD.ExposureBiasValue),
    "MaxApertureValue": ("Exif", piexif.ExifIFD.MaxApertureValue),
    "MeteringMode": ("Exif", piexif.ExifIFD.MeteringMode),
    "Flash": ("Exif", piexif.ExifIFD.Flash),
    "FocalLength": ("Exif", piexif.ExifIFD.FocalLength),
    "ColorSpace": ("Exif", piexif.ExifIFD.ColorSpace),
    "PixelXDimension": ("Exif", piexif.ExifIFD.PixelXDimension),
    "PixelYDimension": ("Exif", piexif.ExifIFD.PixelYDimension),
    "FocalPlaneXResolution": ("Exif", piexif.ExifIFD.FocalPlaneXResolution),
    "FocalPlaneYResolution": ("Exif", piexif.ExifIFD.FocalPlaneYResolution),
    "FocalPlaneResolutionUnit": ("Exif", piexif.ExifIFD.FocalPlaneResolutionUnit),
    "SensingMethod": ("Exif", piexif.ExifIFD.SensingMethod),
    "CustomRendered": ("Exif", piexif.ExifIFD.CustomRendered),
    "ExposureMode": ("Exif", piexif.ExifIFD.ExposureMode),
    "WhiteBalance": ("Exif", piexif.ExifIFD.WhiteBalance),
    "DigitalZoomRatio": ("Exif", piexif.ExifIFD.DigitalZoomRatio),
    "FocalLengthIn35mmFilm": ("Exif", piexif.ExifIFD.FocalLengthIn35mmFilm),
    "SceneCaptureType": ("Exif", piexif.ExifIFD.SceneCaptureType),
    "GainControl": ("Exif", piexif.ExifIFD.GainControl),
    "Contrast": ("Exif", piexif.ExifIFD.Contrast),
    "Saturation": ("Exif", piexif.ExifIFD.Saturation),
    "Sharpness": ("Exif", piexif.ExifIFD.Sharpness),
    "SubjectDistanceRange": ("Exif", piexif.ExifIFD.SubjectDistanceRange),
    "LensMake": ("Exif", piexif.ExifIFD.LensMake),
    "LensModel": ("Exif", piexif.ExifIFD.LensModel),
    "UserComment": ("Exif", piexif.ExifIFD.UserComment),
    "MakerNote": ("Exif", piexif.ExifIFD.MakerNote),
}

_STR_FIELDS = {
    "Make", "Model", "Software", "DateTime", "Artist", "Copyright",
    "DateTimeOriginal", "DateTimeDigitized", "LensMake", "LensModel",
}
_SRATIONAL_FIELDS = {
    "ShutterSpeedValue", "ApertureValue", "ExposureBiasValue",
    "MaxApertureValue", "BrightnessValue",
}
_RATIONAL_FIELDS = {
    "ExposureTime", "FNumber", "FocalLength", "XResolution", "YResolution",
    "FocalPlaneXResolution", "FocalPlaneYResolution", "DigitalZoomRatio",
    "MaxApertureValue",
}
_INT_FIELDS = {
    "Orientation", "ISOSpeedRatings", "Flash", "WhiteBalance", "ExposureMode",
    "MeteringMode", "ExposureProgram", "ColorSpace", "PixelXDimension",
    "PixelYDimension", "SceneCaptureType", "SensingMethod", "CustomRendered",
    "FocalPlaneResolutionUnit", "ResolutionUnit", "YCbCrPositioning",
    "FocalLengthIn35mmFilm", "GainControl", "Contrast", "Saturation",
    "Sharpness", "SubjectDistanceRange",
}


def _to_rational(f, denom=100000):
    """Convert float to (numerator, denominator) EXIF rational tuple."""
    return (int(round(float(f) * denom)), denom)


def encode_value_for_piexif(field_name, value, ifd):
    """Encode a Python value into the correct piexif binary format."""
    if value is None:
        return None

    if field_name in _STR_FIELDS:
        s = value if isinstance(value, str) else str(value)
        return s.encode("utf-8", errors="replace")

    if field_name == "ExifVersion":
        s = str(value).replace(".", "")[:4]
        return s.encode("ascii", errors="replace")

    if field_name == "UserComment":
        s = value if isinstance(value, str) else str(value)
        return b"ASCII\x00\x00\x00" + s.encode("utf-8", errors="replace")

    if field_name in _RATIONAL_FIELDS:
        try:
            return _to_rational(value)
        except Exception:
            return value

    if field_name in _SRATIONAL_FIELDS:
        try:
            return _to_rational(value)
        except Exception:
            return value

    if field_name in _INT_FIELDS:
        try:
            return int(float(value))
        except Exception:
            return value

    return value


def apply_metadata_changes(image_path, changes, remove_gps=False, remove_makernote=False):
    """Apply metadata changes to image and return (out_path, out_name)."""
    out_name = f"modified_{uuid.uuid4().hex[:8]}.jpg"
    out_path = os.path.join(OUTPUT_FOLDER, out_name)

    shutil.copy2(image_path, out_path)

    try:
        exif_dict = piexif.load(out_path)

        if remove_gps:
            exif_dict["GPS"] = {}

        if remove_makernote:
            exif_dict["Exif"].pop(piexif.ExifIFD.MakerNote, None)

        for field, value in changes.items():
            if field.startswith("_") or field not in FIELD_TO_TAG:
                continue
            ifd_name, tag_id = FIELD_TO_TAG[field]
            try:
                encoded = encode_value_for_piexif(field, value, ifd_name)
                if ifd_name in exif_dict:
                    exif_dict[ifd_name][tag_id] = encoded
            except Exception as e:
                print(f"Could not encode {field}: {e}")

        exif_bytes = piexif.dump(exif_dict)
        piexif.insert(exif_bytes, out_path)

    except Exception as e:
        print(f"piexif apply error: {e}")

    return out_path, out_name
