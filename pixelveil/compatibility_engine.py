"""Compatibility scoring, alternative camera finder, and full cascade generator."""

from .config import CAMERAS_DB


def compute_compatibility_score(current_meta_flat, proposed_changes):
    """Score compatibility of proposed_changes vs current metadata. Returns (score 0-100, issues list)."""
    issues = []
    score = 100

    merged = {**current_meta_flat, **proposed_changes}
    make = (merged.get("Make", "") or "").lower()
    model = (merged.get("Model", "") or "").lower()
    software = (merged.get("Software", "") or "").lower()
    lens_make = (merged.get("LensMake", "") or "").lower()

    # Find target camera in DB (exact model first, then fuzzy make+model)
    db_match = None
    db_key = None
    for cam_name, cam_profile in CAMERAS_DB.items():
        if cam_profile.get("Model", "").lower() == model:
            db_match = cam_profile
            db_key = cam_name
            break
    if not db_match:
        for cam_name, cam_profile in CAMERAS_DB.items():
            dm = cam_profile.get("Make", "").lower()
            dd = cam_profile.get("Model", "").lower()
            if (dm in make or make in dm) and (dd in model or model in dd):
                db_match = cam_profile
                db_key = cam_name
                break

    source_make = (current_meta_flat.get("Make", "") or "").lower()
    phone_brands = [
        "apple", "samsung", "xiaomi", "google", "huawei",
        "oppo", "oneplus", "vivo", "realme", "motorola",
    ]
    camera_brands = [
        "canon", "nikon", "sony", "fujifilm", "kodak",
        "eastman", "nikon corporation", "samsung techwin",
        "rollei", "praktica", "medion", "gopro", "dji",
    ]
    source_is_phone = any(b in source_make for b in phone_brands)
    source_is_camera = any(b in source_make for b in camera_brands)

    if db_match:
        target_cat = db_match.get("category", "unknown")

        # 1. Make consistency
        db_make_lower = (db_match.get("Make", "") or "").lower()
        if make and db_make_lower not in make and make not in db_make_lower:
            issues.append({
                "field": "Make",
                "issue": "Make " + repr(merged.get("Make")) + " does not match expected " + repr(db_match["Make"]) + " for " + db_key,
                "severity": "high",
            })
            score -= 25

        # 2. Category mismatch (smartphone vs DSLR/mirrorless/point_and_shoot)
        target_is_camera = target_cat in ["dslr", "mirrorless", "point_and_shoot"]
        target_is_phone = target_cat == "smartphone"
        if source_is_phone and target_is_camera:
            issues.append({
                "field": "Category",
                "issue": "Source is a smartphone but " + db_key + " is a " + target_cat + ". Sensor size, focal length, compression artifacts are fundamentally different — highly detectable.",
                "severity": "high",
            })
            score -= 20
        elif source_is_camera and target_is_phone:
            issues.append({
                "field": "Category",
                "issue": "Source is a camera but " + db_key + " is a smartphone. Focal length, aperture range, and GPS expectations will not match.",
                "severity": "high",
            })
            score -= 20

        # 3. GPS presence
        has_gps = bool(merged.get("GPSLatitude") or merged.get("GPSLatitudeRef"))
        expected_gps = db_match.get("has_gps", False)
        if has_gps and not expected_gps:
            issues.append({
                "field": "GPS",
                "issue": db_key + " typically does NOT embed GPS, but GPS data is present — easily flagged",
                "severity": "high",
            })
            score -= 20
        elif not has_gps and expected_gps:
            issues.append({
                "field": "GPS",
                "issue": db_key + " always embeds GPS, but GPS is absent here — suspicious omission",
                "severity": "medium",
            })
            score -= 10

        # 4. MakerNote — all three cases covered
        has_mn = bool(merged.get("MakerNote"))
        expected_mn = db_match.get("has_makernotes", False)
        if has_mn and not expected_mn:
            issues.append({
                "field": "MakerNote",
                "issue": db_key + " does not use MakerNotes but blob is present — exposes original device signature",
                "severity": "medium",
            })
            score -= 15
        elif has_mn and expected_mn:
            issues.append({
                "field": "MakerNote",
                "issue": "MakerNote binary blob still contains original camera signature — forensically detectable even after field edits",
                "severity": "critical",
            })
            score -= 30
        elif not has_mn and expected_mn:
            issues.append({
                "field": "MakerNote",
                "issue": db_key + " always produces a MakerNote, but it is absent — missing blob flags tampering",
                "severity": "medium",
            })
            score -= 15

        # 5. Software prefix
        sw_prefix = db_match.get("typical_software_prefix") or ""
        if sw_prefix and software and not software.startswith(sw_prefix.lower()):
            issues.append({
                "field": "Software",
                "issue": "Software " + repr(merged.get("Software")) + " does not match expected prefix " + repr(sw_prefix) + " for " + db_key,
                "severity": "medium",
            })
            score -= 15

        # 6. LensMake vs Make
        third_party = ["sigma", "tamron", "tokina", "zeiss", "voigtlander", "samyang", "laowa"]
        if (
            lens_make and make and lens_make not in make and make not in lens_make
            and not any(b in lens_make for b in third_party)
        ):
            issues.append({
                "field": "LensMake",
                "issue": "LensMake " + repr(merged.get("LensMake")) + " inconsistent with Make " + repr(merged.get("Make")),
                "severity": "low",
            })
            score -= 5

    else:
        apple_kw = ["apple", "iphone", "ipad"]
        samsung_kw = ["samsung", "galaxy", "sm-"]
        if any(k in make for k in apple_kw) and not any(k in model for k in apple_kw):
            issues.append({
                "field": "Model",
                "issue": "Make is Apple but Model does not look like an Apple device",
                "severity": "high",
            })
            score -= 25
        elif any(k in make for k in samsung_kw) and not any(k in model for k in samsung_kw):
            issues.append({
                "field": "Model",
                "issue": "Make is samsung but Model does not match Samsung naming pattern",
                "severity": "high",
            })
            score -= 20
        else:
            issues.append({
                "field": "Model",
                "issue": "Camera " + repr(merged.get("Model", model)) + " not found in database — cannot verify metadata consistency",
                "severity": "low",
            })
            score -= 5

    score = max(0, min(100, score))
    return score, issues


def find_alternative_cameras(proposed_model, current_meta_flat, top_n=3):
    """Find cameras similar to proposed model that are more compatible."""
    proposed_profile = None
    for cam_name, profile in CAMERAS_DB.items():
        if cam_name.lower() == proposed_model.lower() or profile.get("Model", "").lower() == proposed_model.lower():
            proposed_profile = profile
            break

    if proposed_profile is None:
        for cam_name, profile in CAMERAS_DB.items():
            if proposed_model.lower() in cam_name.lower():
                proposed_profile = profile
                break

    similar_cameras = []
    if proposed_profile:
        for name in proposed_profile.get("similar_to", []):
            if name in CAMERAS_DB:
                score, issues = compute_compatibility_score(current_meta_flat, {
                    "Make": CAMERAS_DB[name]["Make"],
                    "Model": CAMERAS_DB[name]["Model"],
                    "Software": CAMERAS_DB[name].get("Software", ""),
                })
                similar_cameras.append({
                    "camera": name,
                    "score": score,
                    "issues_count": len(issues),
                    "reason": f"Same manufacturer family, {CAMERAS_DB[name].get('category', 'unknown')} category",
                })

    all_scores = []
    for cam_name, profile in CAMERAS_DB.items():
        score, issues = compute_compatibility_score(current_meta_flat, {
            "Make": profile["Make"],
            "Model": profile["Model"],
            "Software": profile.get("Software", ""),
        })
        all_scores.append({
            "camera": cam_name,
            "score": score,
            "issues_count": len(issues),
            "reason": f"High metadata compatibility ({score}% match)",
        })

    all_scores.sort(key=lambda x: (-x["score"], x["issues_count"]))

    seen = set()
    result = []
    for item in similar_cameras + all_scores:
        if item["camera"] not in seen and item["camera"] != proposed_model:
            seen.add(item["camera"])
            result.append(item)
        if len(result) >= top_n:
            break

    return result


def get_cascade_changes(target_camera_name):
    """Get ALL fields that should change when switching to a target camera.
    Uses the full profile from cameras_db to stamp every EXIF field with
    real values from that camera — this is the complete cascade."""
    if target_camera_name not in CAMERAS_DB:
        for name in CAMERAS_DB:
            if target_camera_name.lower() in name.lower():
                target_camera_name = name
                break
        else:
            return {}

    profile = CAMERAS_DB[target_camera_name]
    changes = {}

    for f in [
        "Make", "Model", "Software", "DateTime",
        "Orientation", "XResolution", "YResolution",
        "ResolutionUnit", "YCbCrPositioning",
    ]:
        v = profile.get(f)
        if v is not None:
            changes[f] = v

    for f in [
        "ExposureTime", "FNumber", "ExposureProgram", "ISOSpeedRatings",
        "ExifVersion", "DateTimeOriginal", "DateTimeDigitized",
        "ShutterSpeedValue", "ApertureValue", "ExposureBiasValue",
        "MaxApertureValue", "MeteringMode", "Flash", "FocalLength",
        "ColorSpace", "PixelXDimension", "PixelYDimension",
        "FocalPlaneXResolution", "FocalPlaneYResolution",
        "FocalPlaneResolutionUnit", "SensingMethod", "CustomRendered",
        "ExposureMode", "WhiteBalance", "DigitalZoomRatio",
        "FocalLengthIn35mmFilm", "SceneCaptureType",
        "GainControl", "Contrast", "Saturation", "Sharpness",
        "SubjectDistanceRange", "LensMake", "LensModel",
    ]:
        v = profile.get(f)
        if v is not None:
            changes[f] = v

    if not profile.get("has_gps", False):
        changes["_remove_gps"] = True
        changes["_gps_note"] = (
            f"{target_camera_name} does not embed GPS — removing GPS block "
            f"prevents location-based detection."
        )

    if not profile.get("has_makernotes", False):
        changes["_remove_makernote"] = True
        changes["_makernote_note"] = (
            f"{target_camera_name} does not produce MakerNotes — stripping "
            f"the blob removes the strongest forensic fingerprint."
        )
    else:
        changes["_makernote_warning"] = (
            f"{target_camera_name} uses MakerNotes ({profile.get('MakerNote_size', 0)} bytes). "
            f"The original device's MakerNote blob cannot be reproduced — stripping it is strongly recommended."
        )

    return changes
