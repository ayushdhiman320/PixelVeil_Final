"""Forensic diff engine and realistic stealth score calculator."""

from .metadata_extractor import flatten_meta


def compute_forensic_diff(original_meta, modified_meta):
    """Compare original vs modified metadata and compute a realistic stealth score."""
    orig_flat = flatten_meta(original_meta)
    mod_flat = flatten_meta(modified_meta)
    all_keys = set(list(orig_flat.keys()) + list(mod_flat.keys()))

    changed = []
    added = []
    removed = []
    unchanged = []

    IGNORE_FIELDS = {
        "FileName", "FileSize", "FileSizeBytes", "FileType", "FileTypeExtension",
        "MIMEType", "ExifByteOrder", "ExifIFDPointer", "GPSInfoIFDPointer",
        "InteroperabilityIFDPointer", "Tag_513", "Tag_514",
        "JpegIFOffset", "JpegIFByteCount",
    }

    EXPECTED_CASCADE_FIELDS = {
        "FocalLength", "FNumber", "ExposureTime", "ISOSpeedRatings", "Flash",
        "MeteringMode", "ExposureProgram", "WhiteBalance", "ExposureMode",
        "ShutterSpeedValue", "ApertureValue", "MaxApertureValue", "ExposureBiasValue",
        "ColorSpace", "DigitalZoomRatio", "FocalLengthIn35mmFilm", "SceneCaptureType",
        "Contrast", "Saturation", "Sharpness", "CustomRendered", "SensingMethod",
        "GainControl", "FocalPlaneXResolution", "FocalPlaneYResolution",
        "FocalPlaneResolutionUnit", "PixelXDimension", "PixelYDimension",
        "XResolution", "YResolution", "ResolutionUnit", "YCbCrPositioning",
        "Orientation", "SubjectDistanceRange", "LensMake", "LensModel",
        "DateTimeDigitized",
    }

    IDENTITY_FIELDS = {"Make", "Model", "Software"}
    TIMESTAMP_FIELDS = {"DateTimeOriginal", "DateTime"}

    for key in sorted(all_keys):
        ov = orig_flat.get(key)
        mv = mod_flat.get(key)
        if ov is None and mv is not None:
            added.append({"field": key, "new_value": str(mv)})
        elif ov is not None and mv is None:
            removed.append({"field": key, "old_value": str(ov)})
        elif str(ov) != str(mv):
            changed.append({"field": key, "old_value": str(ov), "new_value": str(mv)})
        else:
            unchanged.append(key)

    total = len(all_keys)
    modified_count = len(changed) + len(added) + len(removed)

    stealth = 100
    changed_field_names = set()

    for c in changed:
        fname = c["field"].split(".")[-1]
        changed_field_names.add(fname)
        if fname in IGNORE_FIELDS:
            continue
        elif fname in EXPECTED_CASCADE_FIELDS:
            stealth -= 1
        elif fname in IDENTITY_FIELDS:
            stealth -= 5
        elif fname in TIMESTAMP_FIELDS:
            stealth -= 12
        elif fname == "MakerNote":
            stealth -= 35
        else:
            stealth -= 2

    for a in added:
        fname = a["field"].split(".")[-1]
        if fname not in IGNORE_FIELDS:
            stealth -= 3

    for r in removed:
        fname = r["field"].split(".")[-1]
        if fname == "MakerNote":
            stealth += 20
        elif "GPS" in fname:
            stealth += 10
        elif fname not in IGNORE_FIELDS:
            stealth -= 2

    if "Make" in changed_field_names and "Model" in changed_field_names:
        stealth += 8

    stealth = max(0, min(100, stealth))

    risk_indicators = []
    mn_removed = any(r["field"].endswith("MakerNote") for r in removed)
    mn_changed = "MakerNote" in changed_field_names

    if mn_changed:
        risk_indicators.append({
            "label": "MakerNote Mismatch",
            "severity": "critical",
            "detail": "MakerNote blob belongs to original camera — forensically detectable",
        })
    elif mn_removed:
        risk_indicators.append({
            "label": "MakerNote Stripped",
            "severity": "good",
            "detail": "MakerNote removed — eliminates the strongest hardware fingerprint",
        })

    if "Make" in changed_field_names and "Model" not in changed_field_names:
        risk_indicators.append({
            "label": "Make/Model Mismatch",
            "severity": "high",
            "detail": "Make changed but Model unchanged — obvious inconsistency",
        })

    if "DateTimeOriginal" in changed_field_names or "DateTime" in changed_field_names:
        risk_indicators.append({
            "label": "Timestamp Altered",
            "severity": "medium",
            "detail": "DateTime change can be compared against file system creation time",
        })

    if any("GPS" in r["field"] for r in removed):
        risk_indicators.append({
            "label": "GPS Removed",
            "severity": "good",
            "detail": "GPS coordinates stripped — location privacy protected",
        })

    cascade_changes = sum(1 for c in changed if c["field"].split(".")[-1] in EXPECTED_CASCADE_FIELDS)
    if cascade_changes >= 10:
        risk_indicators.append({
            "label": "Full Cascade Applied",
            "severity": "good",
            "detail": f"{cascade_changes} camera settings updated consistently — high internal coherence",
        })

    if modified_count == 0:
        risk_indicators.append({"label": "No Changes", "severity": "info", "detail": "Image is identical to original"})
    elif stealth >= 75:
        risk_indicators.append({"label": "High Stealth", "severity": "good", "detail": "Modifications are well-concealed and internally consistent"})
    elif stealth >= 50:
        risk_indicators.append({"label": "Medium Stealth", "severity": "medium", "detail": "Some detectable inconsistencies remain — consider stripping MakerNote"})
    else:
        risk_indicators.append({"label": "Low Stealth", "severity": "critical", "detail": "High detection risk — MakerNote or timestamp issues detected"})

    meaningful_changes = (
        sum(1 for c in changed if c["field"].split(".")[-1] not in IGNORE_FIELDS)
        + sum(1 for r in removed if r["field"].split(".")[-1] not in IGNORE_FIELDS)
        + sum(1 for a in added if a["field"].split(".")[-1] not in IGNORE_FIELDS)
    )

    return {
        "changed": [c for c in changed if c["field"].split(".")[-1] not in IGNORE_FIELDS],
        "added": [a for a in added if a["field"].split(".")[-1] not in IGNORE_FIELDS],
        "removed": [r for r in removed if r["field"].split(".")[-1] not in IGNORE_FIELDS],
        "unchanged_count": len(unchanged),
        "total_fields": total,
        "modified_count": meaningful_changes,
        "stealth_score": stealth,
        "risk_indicators": risk_indicators,
        "change_percentage": round((meaningful_changes / max(total, 1)) * 100, 1),
    }
