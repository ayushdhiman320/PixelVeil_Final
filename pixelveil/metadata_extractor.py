"""JPEG metadata extraction (File, Image IFD0, EXIF, GPS, Thumbnail, Interop, XMP, Computed)."""

import os
import piexif
from PIL import Image

EXIF_TAG_NAMES = {
    256: "ImageWidth", 257: "ImageLength", 258: "BitsPerSample",
    259: "Compression", 262: "PhotometricInterpretation", 271: "Make",
    272: "Model", 273: "StripOffsets", 274: "Orientation", 277: "SamplesPerPixel",
    278: "RowsPerStrip", 279: "StripByteCounts", 282: "XResolution",
    283: "YResolution", 284: "PlanarConfiguration", 296: "ResolutionUnit",
    301: "TransferFunction", 305: "Software", 306: "DateTime",
    315: "Artist", 316: "HostComputer", 318: "WhitePoint",
    319: "PrimaryChromaticities", 529: "YCbCrCoefficients",
    530: "YCbCrSubSampling", 531: "YCbCrPositioning",
    532: "ReferenceBlackWhite", 700: "XMP", 33432: "Copyright",
    33434: "ExposureTime", 33437: "FNumber", 34665: "ExifIFDPointer",
    34850: "ExposureProgram", 34852: "SpectralSensitivity",
    34853: "GPSInfoIFDPointer", 34855: "ISOSpeedRatings",
    34856: "OECF", 36864: "ExifVersion", 36867: "DateTimeOriginal",
    36868: "DateTimeDigitized", 37121: "ComponentsConfiguration",
    37122: "CompressedBitsPerPixel", 37377: "ShutterSpeedValue",
    37378: "ApertureValue", 37379: "BrightnessValue",
    37380: "ExposureBiasValue", 37381: "MaxApertureValue",
    37382: "SubjectDistance", 37383: "MeteringMode", 37384: "LightSource",
    37385: "Flash", 37386: "FocalLength", 37396: "SubjectArea",
    37500: "MakerNote", 37510: "UserComment", 37520: "SubSecTime",
    37521: "SubSecTimeOriginal", 37522: "SubSecTimeDigitized",
    40960: "FlashPixVersion", 40961: "ColorSpace", 40962: "PixelXDimension",
    40963: "PixelYDimension", 40964: "RelatedSoundFile",
    40965: "InteroperabilityIFDPointer", 41483: "FlashEnergy",
    41484: "SpatialFrequencyResponse", 41486: "FocalPlaneXResolution",
    41487: "FocalPlaneYResolution", 41488: "FocalPlaneResolutionUnit",
    41492: "SubjectLocation", 41493: "ExposureIndex", 41495: "SensingMethod",
    41728: "FileSource", 41729: "SceneType", 41730: "CFAPattern",
    41985: "CustomRendered", 41986: "ExposureMode", 41987: "WhiteBalance",
    41988: "DigitalZoomRatio", 41989: "FocalLengthIn35mmFilm",
    41990: "SceneCaptureType", 41991: "GainControl", 41992: "Contrast",
    41993: "Saturation", 41994: "Sharpness", 41995: "DeviceSettingDescription",
    41996: "SubjectDistanceRange", 42016: "ImageUniqueID",
    42032: "CameraOwnerName", 42033: "BodySerialNumber",
    42034: "LensSpecification", 42035: "LensMake", 42036: "LensModel",
    42037: "LensSerialNumber",
}

GPS_TAG_NAMES = {
    0: "GPSVersionID", 1: "GPSLatitudeRef", 2: "GPSLatitude",
    3: "GPSLongitudeRef", 4: "GPSLongitude", 5: "GPSAltitudeRef",
    6: "GPSAltitude", 7: "GPSTimeStamp", 8: "GPSSatellites",
    9: "GPSStatus", 10: "GPSMeasureMode", 11: "GPSDOP",
    12: "GPSSpeedRef", 13: "GPSSpeed", 14: "GPSTrackRef",
    15: "GPSTrack", 16: "GPSImgDirectionRef", 17: "GPSImgDirection",
    18: "GPSMapDatum", 19: "GPSDestLatitudeRef", 20: "GPSDestLatitude",
    21: "GPSDestLongitudeRef", 22: "GPSDestLongitude",
    23: "GPSDestBearingRef", 24: "GPSDestBearing",
    25: "GPSDestDistanceRef", 26: "GPSDestDistance",
    27: "GPSProcessingMethod", 28: "GPSAreaInformation",
    29: "GPSDateStamp", 30: "GPSDifferential",
}


def rational_to_float(val):
    if isinstance(val, tuple) and len(val) == 2:
        if val[1] == 0:
            return 0.0
        return round(val[0] / val[1], 6)
    return val


def decode_value(tag_id, val):
    """Decode raw piexif value to human-readable."""
    if isinstance(val, bytes):
        try:
            decoded = val.rstrip(b"\x00").decode("utf-8", errors="replace")
            if decoded.isprintable() or decoded.strip():
                return decoded
        except Exception:
            pass
        return f"<binary {len(val)} bytes>"
    if isinstance(val, tuple):
        if len(val) == 2 and isinstance(val[0], int) and isinstance(val[1], int):
            return rational_to_float(val)
        return [decode_value(tag_id, v) for v in val]
    return val


def extract_all_metadata(image_path):
    """Extract all available metadata from JPEG."""
    metadata = {
        "File": {},
        "EXIF": {},
        "GPS": {},
        "Image": {},
        "Thumbnail": {},
        "Interop": {},
        "Computed": {},
    }

    stat = os.stat(image_path)
    metadata["File"]["FileName"] = os.path.basename(image_path)
    metadata["File"]["FileSize"] = f"{stat.st_size:,} bytes"
    metadata["File"]["FileSizeBytes"] = stat.st_size
    metadata["File"]["FileType"] = "JPEG"
    metadata["File"]["MIMEType"] = "image/jpeg"

    try:
        with Image.open(image_path) as img:
            metadata["File"]["ImageWidth"] = img.width
            metadata["File"]["ImageHeight"] = img.height
            metadata["File"]["Mode"] = img.mode
            metadata["Computed"]["MegaPixels"] = round((img.width * img.height) / 1_000_000, 2)
            metadata["Computed"]["AspectRatio"] = f"{img.width}:{img.height}"

            try:
                xmp_data = img.info.get("xmp", None)
                if xmp_data:
                    xmp_str = xmp_data.decode("utf-8", errors="replace") if isinstance(xmp_data, bytes) else str(xmp_data)
                    metadata["XMP"] = {"RawXMP": xmp_str[:2000]}
            except Exception:
                pass
    except Exception as e:
        metadata["File"]["Error"] = str(e)

    try:
        exif_dict = piexif.load(image_path)

        for tag_id, raw_val in exif_dict.get("0th", {}).items():
            tag_name = EXIF_TAG_NAMES.get(tag_id, f"Tag_{tag_id}")
            metadata["Image"][tag_name] = decode_value(tag_id, raw_val)

        for tag_id, raw_val in exif_dict.get("Exif", {}).items():
            tag_name = EXIF_TAG_NAMES.get(tag_id, f"Tag_{tag_id}")
            if tag_name == "MakerNote":
                metadata["EXIF"]["MakerNote"] = (
                    f"<MakerNote binary {len(raw_val) if isinstance(raw_val, bytes) else '?'} bytes>"
                )
            else:
                metadata["EXIF"][tag_name] = decode_value(tag_id, raw_val)

        gps_ifd = exif_dict.get("GPS", {})
        if gps_ifd:
            for tag_id, raw_val in gps_ifd.items():
                tag_name = GPS_TAG_NAMES.get(tag_id, f"GPSTag_{tag_id}")
                metadata["GPS"][tag_name] = decode_value(tag_id, raw_val)

        for tag_id, raw_val in exif_dict.get("1st", {}).items():
            tag_name = EXIF_TAG_NAMES.get(tag_id, f"Tag_{tag_id}")
            metadata["Thumbnail"][tag_name] = decode_value(tag_id, raw_val)
        if exif_dict.get("thumbnail"):
            metadata["Thumbnail"]["ThumbnailPresent"] = True
            metadata["Thumbnail"]["ThumbnailSize"] = f"{len(exif_dict['thumbnail'])} bytes"

        for tag_id, raw_val in exif_dict.get("Interop", {}).items():
            metadata["Interop"][f"Tag_{tag_id}"] = decode_value(tag_id, raw_val)

    except Exception as e:
        metadata["EXIF"]["_error"] = f"piexif error: {str(e)}"

    return {k: v for k, v in metadata.items() if v}


def flatten_meta(meta_dict, prefix=""):
    """Flatten nested metadata dict. Keys are 'Group.Field'."""
    result = {}
    for group, fields in meta_dict.items():
        if isinstance(fields, dict):
            for field, val in fields.items():
                result[f"{group}.{field}"] = val
        else:
            result[group] = fields
    return result


def flatten_meta_plain(meta_dict):
    """Flatten to plain field names (last-write-wins for duplicates).
    Used for compatibility scoring so we can look up 'Make' not 'Image.Make'."""
    result = {}
    for group, fields in meta_dict.items():
        if isinstance(fields, dict):
            for field, val in fields.items():
                result[field] = val
    return result
