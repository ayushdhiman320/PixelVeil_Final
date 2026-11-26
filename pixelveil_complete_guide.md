# PixelVeil — Complete Project & Technical Guide
**Anti-Forensic JPEG Metadata Manipulation & AI Compatibility System**  
*Prepared for Digital Forensics Faculty Presentation*

---

## 1. Project Overview

**PixelVeil** is an anti-forensic digital forensics tool designed to inspect, analyze, and coherently modify JPEG metadata.

Unlike naive EXIF editors that change only `Make` or `Model` (leaving behind dozens of contradictory clues), PixelVeil:
1. Extracts **all** embedded metadata groups from a JPEG (`File`, `Image`, `EXIF`, `GPS`, `Thumbnail`, `Interop`, `XMP`, `Computed`).
2. Evaluates any proposed edit with a **rule-based Compatibility Scoring Engine** backed by real camera profiles extracted from `test_image/`.
3. Uses a **Groq LLM AI Agent (`openai/gpt-oss-120b`)** to explain forensic risks in plain language and recommend safer camera alternatives.
4. Applies a **Full Cascade** (31–39 coordinated EXIF fields + GPS/MakerNote stripping) so every modified tag matches the target camera's real hardware/firmware profile.
5. Writes changes directly into the JPEG binary structure (`piexif`) so they appear in **Windows File Properties → Details** and forensic tools.
6. Computes a **Forensic Diff & Stealth Score (0–100)** comparing the original vs. modified image.

---

## 2. Project Directory Structure

```text
E:\PixelVeil_Final\
│
├── app.py                          # Slim Flask server & REST API routes (port 8080)
├── cameras_db.json                 # Real EXIF profiles for the 6 cameras in test_image/
├── pixelveil_config.txt            # Stores GROQ_API_KEY (kept out of source code)
├── requirements.txt                # Python dependencies (flask, flask-cors, pillow, piexif, groq)
├── start.bat                       # Windows one-click launcher (runs python app.py on :8080)
│
├── pixelveil/                      # Modular backend engine package
│   ├── __init__.py                 # Package marker
│   ├── config.py                   # Paths, CAMERAS_DB loader, GROQ_API_KEY loader, SESSIONS
│   ├── metadata_extractor.py       # Reads all JPEG metadata groups & flattens dicts
│   ├── compatibility_engine.py     # Compatibility scoring, alternative finder, cascade builder
│   ├── ai_agent.py                 # Groq LLM integration & JSON response parser
│   ├── forensic_diff.py            # Original vs modified diff & Stealth Score algorithm
│   └── metadata_writer.py          # Binary EXIF encoder & piexif JPEG writer
│
├── static/                         # Single-page web frontend
│   ├── index.html                  # UI layout, upload zone, modals, diff & agent panels
│   ├── style.css                   # Dark glassmorphism theme & dark dropdown styling
│   └── app.js                      # Frontend state, AJAX calls, live compat & cascade UI
│
├── test_image/                     # Real camera images (Dresden dataset + user's phone)
│   ├── Canon_PowerShotA640/        # Canon PowerShot A640 (point-and-shoot)
│   ├── Kodak_M1063_0/              # Kodak EasyShare M1063 (point-and-shoot)
│   ├── Nikon_D70/                  # Nikon D70 (DSLR)
│   ├── Samsung_NV15/               # Samsung NV15 (point-and-shoot)
│   ├── Sony_DSC_W170/              # Sony DSC-W170 (point-and-shoot)
│   └── my_phone/                   # Xiaomi 22111317I (Redmi Note 12 Pro smartphone)
│
├── uploads/                        # Uploaded original JPEGs per session
└── outputs/                        # Generated modified JPEGs ready for download
```

---

## 3. End-to-End Execution & Data Flow

```text
[1] Browser opens http://localhost:8080  ──► app.py serves static/index.html
         │
         ▼
[2] User uploads a JPEG image
    POST /api/upload
         ├── Saves original to uploads/<session_id>_original.jpg
         ├── metadata_extractor.extract_all_metadata() reads all IFDs + PIL + XMP
         └── Stores original_meta & current_meta in SESSIONS[session_id]
         │
         ▼
[3] User clicks a field (e.g., Model) and types or picks a target camera
    ├── (a) Live Compatibility Check: POST /api/check-compatibility
    │       └── compatibility_engine.compute_compatibility_score() → 0–100% + issues
    │
    ├── (b) Full Cascade Preview (when camera picked from dropdown): POST /api/get-cascade
    │       └── compatibility_engine.get_cascade_changes() → 31–39 coordinated EXIF fields
    │
    └── (c) Ask AI Agent: POST /api/agent-suggest
            ├── Runs compute_compatibility_score()
            ├── ai_agent.call_groq_agent() sends key metadata + DB summary to Groq LLM
            └── Returns analysis, top 3 risks, 3 safer alternatives, must-change fields, verdict
         │
         ▼
[4] User clicks "Apply Changes to Image"
    POST /api/apply-changes
         ├── metadata_writer.apply_metadata_changes() copies original → outputs/modified_<id>.jpg
         ├── Strips GPS and/or MakerNote if flagged
         ├── Encodes all staged fields to EXIF binary & inserts via piexif.insert()
         └── Re-extracts metadata from the new file to confirm actual written tags
         │
         ▼
[5] Automatic Forensic Diff & Download
    POST /api/forensic-diff
         ├── forensic_diff.compute_forensic_diff(original_meta, current_meta)
         └── Displays Stealth Score (0–100), risk indicators, and field-by-field diff table
    GET /api/download/<filename>
         └── Downloads modified_<id>.jpg (verifiable in Windows Properties → Details)
```

---

## 4. Module-by-Module & Function Explanation

### A. `app.py` (Flask Entry Point & REST API)
Keeps only HTTP routing and session orchestration:
- `serve_index()` / `serve_static(path)`: Serves the frontend from `static/`.
- `upload_image()` (`POST /api/upload`): Validates `.jpg`/`.jpeg`, saves to `uploads/`, extracts metadata, initializes `SESSIONS[session_id]`.
- `check_compatibility()` (`POST /api/check-compatibility`): Flattens current metadata (`flatten_meta_plain`) and returns compatibility score, issues, risk level (`low`/`medium`/`high`), and alternative cameras.
- `agent_suggest()` (`POST /api/agent-suggest`): Collects key metadata fields, computes compatibility score, calls `call_groq_agent()`, and attaches `get_cascade_changes()` if `Make`/`Model` changed.
- `get_cascade()` (`POST /api/get-cascade`): Returns all cascade fields and GPS/MakerNote flags for a selected camera.
- `apply_changes()` (`POST /api/apply-changes`): Calls `apply_metadata_changes()` on the original image, re-extracts metadata from the output JPEG, updates `SESSIONS`.
- `forensic_diff()` (`POST /api/forensic-diff`): Calls `compute_forensic_diff(original_meta, current_meta)`.
- `download_file(filename)` (`GET /api/download/<filename>`): Sends the modified JPEG from `outputs/`.
- `list_cameras()` (`GET /api/cameras`): Returns the list of cameras in `cameras_db.json`.

---

### B. `pixelveil/config.py` (Configuration & State)
- Defines `UPLOAD_FOLDER`, `OUTPUT_FOLDER`, `CAMERAS_DB_PATH`, and `CONFIG_PATH`.
- Loads `cameras_db.json` into `CAMERAS_DB`.
- Loads `GROQ_API_KEY` from environment variable first, falling back to `pixelveil_config.txt`.
- Holds the in-memory `SESSIONS` dictionary.

---

### C. `pixelveil/metadata_extractor.py` (Full Metadata Extraction)
- `EXIF_TAG_NAMES` & `GPS_TAG_NAMES`: Lookup dictionaries mapping numeric EXIF/GPS tag IDs (e.g., `271 → Make`, `37500 → MakerNote`) to readable names.
- `rational_to_float(val)` & `decode_value(tag_id, val)`: Converts raw EXIF bytes to UTF-8 strings and `(numerator, denominator)` rational tuples to floats.
- `extract_all_metadata(image_path)`:
  - **File**: filename, size in bytes, dimensions, color mode (`RGB`).
  - **Computed**: `MegaPixels`, `AspectRatio`.
  - **XMP**: Extracts raw XMP packet if embedded in `img.info`.
  - **Image (`0th` IFD)**: `Make`, `Model`, `Software`, `Orientation`, `XResolution`, `YResolution`, `DateTime`, etc.
  - **EXIF (`Exif` IFD)**: `ExposureTime`, `FNumber`, `ISOSpeedRatings`, `FocalLength`, `Flash`, `ColorSpace`, `DateTimeOriginal`, and detects `MakerNote` binary blob size.
  - **GPS (`GPS` IFD)**, **Thumbnail (`1st` IFD)**, **Interop (`Interop` IFD)**.
- `flatten_meta(meta_dict)`: Flattens to `"Group.Field"` keys (used by Forensic Diff).
- `flatten_meta_plain(meta_dict)`: Flattens to plain `"Field"` keys (used by Compatibility Scorer).

---

### D. `pixelveil/compatibility_engine.py` (Scoring, Alternatives & Cascade)
Contains three core functions:

1. **`compute_compatibility_score(current_meta_flat, proposed_changes)`**  
   Evaluates how forensically plausible a proposed edit is (starts at `100`, clamped to `0–100`).
2. **`find_alternative_cameras(proposed_model, current_meta_flat, top_n=3)`**  
   Combines the target camera's `similar_to` list from `cameras_db.json` with a full compatibility scan across all 6 cameras, sorting by highest score and fewest issues.
3. **`get_cascade_changes(target_camera_name)`**  
   Builds the full list of fields to stamp when switching to a target camera (explained in Section 7).

---

### E. `pixelveil/ai_agent.py` (Groq AI Agent)
- **`call_groq_agent(session_meta_flat, field_changed, old_value, new_value, compatibility_score, issues)`**:
  - Uses the Groq Python SDK with model `openai/gpt-oss-120b` (`temperature=0.2`, `max_tokens=1200`).
  - Sends a structured prompt containing:
    1. Compact profiles of all 6 real cameras in `cameras_db.json` (Make, Model, category, GPS, MakerNote size, FocalLength, FNumber, ISO, Flash, ColorSpace, resolution, forensic notes).
    2. Key metadata fields of the uploaded image.
    3. The exact user edit (`field_changed`: `old_value` → `new_value`).
    4. The rule-based `compatibility_score` and `issues` already detected.
  - Instructs the LLM to return **strict JSON** containing:
    - `analysis`: 2–3 sentence explanation of the risks.
    - `forensic_risks`: Top 3 concrete detection risks.
    - `alternatives`: 3 safer camera options strictly from `cameras_db.json` with scores and reasons.
    - `must_change_fields`: Key fields that must be updated together.
    - `recommendation`: `"proceed"`, `"change_model"`, or `"abort"` + `recommendation_reason`.
  - Extracts the `{...}` JSON block safely and handles empty/malformed responses gracefully.

---

### F. `pixelveil/forensic_diff.py` (Diff & Stealth Score)
- **`compute_forensic_diff(original_meta, modified_meta)`**:
  - Compares every key in `original_meta` vs `modified_meta` into `changed`, `added`, `removed`, and `unchanged`.
  - Filters out internal file/pointer fields (`IGNORE_FIELDS`) from the meaningful diff count so structural EXIF offset shifts don't distort the result.
  - Computes `stealth_score` (0–100) and qualitative `risk_indicators` (`MakerNote Stripped`, `Full Cascade Applied`, `Timestamp Altered`, `GPS Removed`, `High/Medium/Low Stealth`).

---

### G. `pixelveil/metadata_writer.py` (Modifying the Actual JPEG)
- **`FIELD_TO_TAG`**: Maps 45+ field names to their exact `(IFD, piexif tag ID)` (e.g., `"Make" → ("0th", piexif.ImageIFD.Make)`, `"FocalLength" → ("Exif", piexif.ExifIFD.FocalLength)`).
- **`encode_value_for_piexif(field_name, value, ifd)`**:
  - `_STR_FIELDS` → UTF-8 encoded `bytes`
  - `ExifVersion` → 4-byte ASCII (`b"0221"`)
  - `UserComment` → `b"ASCII\x00\x00\x00"` prefix + UTF-8 bytes
  - `_RATIONAL_FIELDS` & `_SRATIONAL_FIELDS` → `(int(round(float(val) * 100000)), 100000)` EXIF rational tuples
  - `_INT_FIELDS` → `int(float(value))`
- **`apply_metadata_changes(image_path, changes, remove_gps=False, remove_makernote=False)`**:
  1. Copies original image to `outputs/modified_<8-hex>.jpg` (never overwrites original).
  2. Loads binary EXIF via `piexif.load(out_path)`.
  3. Clears `exif_dict["GPS"] = {}` if `remove_gps=True`.
  4. Pops `piexif.ExifIFD.MakerNote` from `exif_dict["Exif"]` if `remove_makernote=True`.
  5. Encodes and writes every field in `changes` into `exif_dict[ifd_name][tag_id]`.
  6. Serializes with `piexif.dump(exif_dict)` and embeds back into the JPEG via `piexif.insert(exif_bytes, out_path)`.

---

## 5. How Compatibility Risk Score & Stealth Score Algorithms Work

PixelVeil uses **two complementary scoring algorithms** at different stages:

### 1. Compatibility Score (Pre-edit Risk Check — `compatibility_engine.py`)
Starts at **100** and deducts points based on 6 forensic consistency checks against `cameras_db.json`:

| Check | Condition | Penalty | Severity |
|---|---|---|---|
| **1. Make Consistency** | `Make` does not match the target model's manufacturer in DB | **-25** | `high` |
| **2. Category Mismatch** | Switching Smartphone ↔ DSLR / Point-and-Shoot (sensor & optics mismatch) | **-20** | `high` |
| **3. GPS Expectation** | GPS present when target camera has `has_gps: false` (**-20**) or absent when `has_gps: true` (**-10**) | **-10 to -20** | `high` / `medium` |
| **4. MakerNote Check** | Blob present & target uses MakerNote (**-30** — original camera signature leaks!); blob present & target doesn't (**-15**); blob absent & target expects it (**-15**) | **-15 to -30** | `critical` / `medium` |
| **5. Software Prefix** | `Software` doesn't match target camera's expected prefix (e.g., `Ver.` for Nikon) | **-15** | `medium` |
| **6. LensMake vs Make** | `LensMake` conflicts with `Make` (ignoring 3rd-party lenses like Sigma/Tamron) | **-5** | `low` |

**Risk Level Mapping:**
- `75 – 100` → **Low Risk**
- `50 – 74` → **Medium Risk**
- `0 – 49` → **High Risk**

---

### 2. Stealth Score (Post-edit Forensic Diff — `forensic_diff.py`)
Starts at **100** and measures how detectable the final modified file is:

- **Ignored (`0` penalty):** `IGNORE_FIELDS` such as `FileName`, `FileSize`, `ExifIFDPointer`, `InteroperabilityIFDPointer`, and thumbnail offset tags (`Tag_513`, `Tag_514`) — these are normal container/filesystem artifacts, not tampering clues.
- **Expected Cascade Camera Settings (`-1` each):** `FocalLength`, `FNumber`, `ExposureTime`, `ISOSpeedRatings`, `Flash`, `MeteringMode`, `ColorSpace`, `WhiteBalance`, `PixelXDimension`, `PixelYDimension`, etc. Changing them together creates internal coherence rather than suspicion.
- **Identity Fields (`-5` each):** `Make`, `Model`, `Software`.
- **Timestamp Fields (`-12` each):** `DateTimeOriginal`, `DateTime` (can be cross-checked against OS file timestamps).
- **MakerNote Still Modified/Present (`-35`):** Strongest hardware fingerprint mismatch.
- **Added Unknown Field (`-3` each)** / **Removed Other Field (`-2` each)**.
- **Anti-Forensic Bonuses:**
  - **MakerNote Stripped:** `+20` (eliminates original device binary signature)
  - **GPS Removed:** `+10` (protects location & matches non-GPS cameras)
  - **Make + Model Changed Together:** `+8` (avoids partial-edit mismatch)

---

## 6. How Cascade Field Selection Works

When you pick a target camera from the dropdown (or via the AI Agent), `get_cascade_changes(target_camera_name)` selects **all coordinated fields** from that camera's real profile in `cameras_db.json`:

1. **IFD0 Identity & Image Structure (9 fields):**  
   `Make`, `Model`, `Software`, `DateTime`, `Orientation`, `XResolution`, `YResolution`, `ResolutionUnit`, `YCbCrPositioning`.
2. **EXIF Optics, Exposure & Sensor Settings (up to 30 fields):**  
   `ExposureTime`, `FNumber`, `ExposureProgram`, `ISOSpeedRatings`, `ExifVersion`, `DateTimeOriginal`, `DateTimeDigitized`, `ShutterSpeedValue`, `ApertureValue`, `ExposureBiasValue`, `MaxApertureValue`, `MeteringMode`, `Flash`, `FocalLength`, `ColorSpace`, `PixelXDimension`, `PixelYDimension`, `FocalPlaneXResolution`, `FocalPlaneYResolution`, `FocalPlaneResolutionUnit`, `SensingMethod`, `CustomRendered`, `ExposureMode`, `WhiteBalance`, `DigitalZoomRatio`, `FocalLengthIn35mmFilm`, `SceneCaptureType`, `GainControl`, `Contrast`, `Saturation`, `Sharpness`, `SubjectDistanceRange`, `LensMake`, `LensModel`.
3. **Automatic Binary Stripping Flags:**
   - If `has_gps` is `false` → sets `_remove_gps = True` (clears entire GPS IFD).
   - If `has_makernotes` is `false` → sets `_remove_makernote = True` (strips MakerNote).
   - If `has_makernotes` is `true` → sets `_makernote_warning` and the frontend (`static/app.js`) still passes `remove_makernote = True` when applying so the original camera's MakerNote blob never leaks inside the spoofed image.

**Why this matters:** In our database of 6 real cameras, selecting a camera automatically stages **31 to 39 real, matched EXIF fields** in one click instead of changing just 1 or 2 fields.

---

## 7. How We Tested & Verified the Project

1. **Real Dataset Grounding (`test_image/`):**
   - Extracted actual EXIF profiles from 5 Dresden Image Database cameras (`Canon PowerShot A640`, `Kodak EasyShare M1063`, `Nikon D70`, `Samsung NV15`, `Sony DSC-W170`) plus the user's real smartphone (`Xiaomi 22111317I`) into `cameras_db.json`.
2. **End-to-End API Pipeline Test (`app.test_client()`):**
   - Tested all endpoints directly on the modular codebase using a real `Kodak_M1063_0_9369.jpg` → `Nikon D70` conversion:
     - `GET /api/cameras` → `6` cameras returned (`200 OK`)
     - `POST /api/upload` → `6` metadata groups extracted (`Computed`, `EXIF`, `File`, `Image`, `Interop`, `Thumbnail`)
     - `POST /api/check-compatibility` → `45%` compatibility score (`high` risk due to Make/MakerNote mismatch)
     - `POST /api/get-cascade` → `37` coordinated Nikon D70 fields returned
     - `POST /api/apply-changes` → wrote `outputs/modified_86205ed1.jpg` (`success: True`)
     - `POST /api/forensic-diff` → **Stealth Score: `82/100`** (`22` meaningful fields updated, `MakerNote Stripped`, `Full Cascade Applied`, `High Stealth`)
     - `GET /api/download/modified_86205ed1.jpg` → `1,824,801` bytes downloadable JPEG
3. **Groq AI Agent Verification:**
   - Verified live calls to `openai/gpt-oss-120b` return structured JSON with real database camera recommendations, risk explanations, and null-safe frontend rendering.
4. **Windows Properties & UI Verification:**
   - Verified `piexif.insert()` writes standard IFD0 and EXIF tags (`Make`, `Model`, `FocalLength`, `FNumber`, `ISOSpeedRatings`, `ExposureTime`, `Flash`, etc.) so they appear in Windows **Properties → Details**.
   - Verified dark dropdown readability (`select.field-input option`) and server access on `http://localhost:8080`.

---

## 8. Quick Presentation Demo Checklist

1. Run `python app.py` (or double-click `start.bat`) and open **`http://localhost:8080`** in Chrome.
2. Upload any photo from `test_image/my_phone/` or `test_image/Kodak_M1063_0/`.
3. Click **Edit** on `Model` → type or pick **`Nikon D70`** → show the **Compatibility Score** drop and forensic warnings.
4. Click **🤖 Ask AI Agent** → show Groq AI's live risk breakdown and safer camera alternatives.
5. Click **📋 Preview Cascade** → **Apply Cascade** → show 30+ fields staged together.
6. Click **Apply Changes to Image** → show the **Forensic Diff** (`Stealth Score`, `MakerNote Stripped`, `Full Cascade Applied`) and **Download Modified JPEG**.
7. *(Optional)* Right-click the downloaded JPEG in Windows Explorer → **Properties → Details** to prove the camera metadata actually changed on disk.

---

## 9. Function-by-Function Viva & Code Explanation Cheat Sheet

If faculty opens any file and asks *"Explain what this function does"*, use the quick reference below:

### `pixelveil/metadata_extractor.py`
- **`rational_to_float(val)`**
  - **Input:** EXIF rational tuple `(numerator, denominator)` (e.g., `(1, 250)`).
  - **What it does:** Checks for divide-by-zero (`val[1] == 0`), otherwise returns `round(val[0] / val[1], 6)` so values like shutter speed or focal length become clean decimal numbers.
- **`decode_value(tag_id, val)`**
  - **Input:** Raw tag ID and value returned by `piexif.load()`.
  - **What it does:** Converts raw `bytes` to UTF-8 strings (stripping null `\x00` padding), converts rational tuples using `rational_to_float()`, and recursively decodes nested tuples/lists. If a byte blob isn't printable text, returns `<binary N bytes>`.
- **`extract_all_metadata(image_path)`**
  - **Input:** Path to a JPEG file.
  - **What it does:** Collects metadata from 3 sources into grouped dictionaries (`File`, `Computed`, `XMP`, `Image`, `EXIF`, `GPS`, `Thumbnail`, `Interop`):
    1. `os.stat()` → filename and byte size.
    2. `PIL.Image.open()` → pixel dimensions, color mode, `MegaPixels`, `AspectRatio`, and raw `XMP` XML if present.
    3. `piexif.load()` → loops over `0th` (Image), `Exif`, `GPS`, `1st` (Thumbnail), and `Interop` IFDs, translating numeric tag IDs via `EXIF_TAG_NAMES` / `GPS_TAG_NAMES`. Special-cases `MakerNote` to report its binary byte size instead of raw gibberish.
- **`flatten_meta(meta_dict)`**
  - **What it does:** Converts nested `{"EXIF": {"FocalLength": 7.3}}` into `{"EXIF.FocalLength": 7.3}` so `compute_forensic_diff()` can compare every group+field uniquely.
- **`flatten_meta_plain(meta_dict)`**
  - **What it does:** Converts nested metadata into flat keys without group prefixes (`{"FocalLength": 7.3}`) so `compute_compatibility_score()` can look up `"Make"`, `"Model"`, `"MakerNote"`, etc. directly.

### `pixelveil/compatibility_engine.py`
- **`compute_compatibility_score(current_meta_flat, proposed_changes)`**
  - **Input:** Flattened current metadata + dict of proposed edits (e.g., `{"Model": "NIKON D70"}`).
  - **What it does:** Merges proposed edits onto current metadata, matches the target camera in `CAMERAS_DB` (exact model match first, fuzzy make+model fallback), and runs 6 forensic consistency checks (Make mismatch `-25`, Smartphone↔Camera category mismatch `-20`, GPS expectation `-10/-20`, MakerNote presence/mismatch `-15/-30`, Software prefix `-15`, LensMake `-5`). Returns `(score, issues)` clamped to `0–100`.
- **`find_alternative_cameras(proposed_model, current_meta_flat, top_n=3)`**
  - **Input:** The model the user tried to set + current image metadata.
  - **What it does:** Looks up `similar_to` cameras from `CAMERAS_DB`, scores every camera in the DB using `compute_compatibility_score()`, sorts by highest score and fewest issues, deduplicates, and returns the top 3 safer alternatives.
- **`get_cascade_changes(target_camera_name)`**
  - **Input:** Target camera name (e.g., `"Nikon D70"`).
  - **What it does:** Reads the full real EXIF profile from `CAMERAS_DB` and collects up to 39 coordinated `IFD0` + `EXIF` fields (`Make`, `Model`, `FocalLength`, `FNumber`, `ISOSpeedRatings`, `Flash`, `ColorSpace`, etc.), plus `_remove_gps` and `_remove_makernote` / `_makernote_warning` flags so the entire metadata profile stays internally consistent.

### `pixelveil/ai_agent.py`
- **`call_groq_agent(session_meta_flat, field_changed, old_value, new_value, compatibility_score, issues)`**
  - **Input:** Key metadata fields, the user's edit, and the rule-based score/issues.
  - **What it does:** Builds a structured prompt containing all 6 camera profiles from `CAMERAS_DB` and the current image's key tags, calls Groq's `openai/gpt-oss-120b` model (`temperature=0.2`), extracts the JSON `{...}` block from the LLM response, and returns `analysis`, `forensic_risks`, `alternatives`, `must_change_fields`, and `recommendation`.

### `pixelveil/forensic_diff.py`
- **`compute_forensic_diff(original_meta, modified_meta)`**
  - **Input:** `original_meta` and `current_meta` dictionaries from the session.
  - **What it does:** Flattens both dicts and classifies every key into `changed`, `added`, `removed`, or `unchanged`. Ignores container/pointer artifacts (`IGNORE_FIELDS` like `FileName`, `FileSize`, `ExifIFDPointer`), applies weighted penalties (`-1` for expected cascade fields, `-5` for identity, `-12` for timestamps, `-35` for MakerNote mismatch) and bonuses (`+20` MakerNote stripped, `+10` GPS removed, `+8` Make+Model changed together), and outputs `stealth_score`, `risk_indicators`, and `change_percentage`.

### `pixelveil/metadata_writer.py`
- **`_to_rational(f, denom=100000)`**
  - **What it does:** Converts a Python float (e.g., `7.3`) into an EXIF rational tuple `(730000, 100000)` required by `piexif`.
- **`encode_value_for_piexif(field_name, value, ifd)`**
  - **What it does:** Converts each Python value into the exact binary representation expected by EXIF specs: UTF-8 `bytes` for strings, 4-byte ASCII for `ExifVersion`, `ASCII\x00\x00\x00` header for `UserComment`, `(num, denom)` tuples for rational/signed-rational fields, and `int` for integer tags.
- **`apply_metadata_changes(image_path, changes, remove_gps=False, remove_makernote=False)`**
  - **Input:** Original image path, dict of field changes, and strip flags.
  - **What it does:** Copies the original JPEG to `outputs/modified_<id>.jpg`, loads EXIF via `piexif.load()`, clears `GPS` if `remove_gps`, pops `MakerNote` if `remove_makernote`, encodes and writes all fields in `FIELD_TO_TAG`, serializes with `piexif.dump()`, and embeds the new EXIF header into the JPEG using `piexif.insert()`.

### `app.py` (Flask Routes)
- **`upload_image()`**: Saves uploaded JPEG, runs `extract_all_metadata()`, creates a new session in `SESSIONS`.
- **`check_compatibility()`**: Runs `compute_compatibility_score()` + `find_alternative_cameras()` for live preview as the user types.
- **`agent_suggest()`**: Runs `compute_compatibility_score()`, `call_groq_agent()`, and `get_cascade_changes()`.
- **`get_cascade()`**: Returns `get_cascade_changes(target_camera)` when the user selects a camera from the dropdown.
- **`apply_changes()`**: Calls `apply_metadata_changes()` on the original image, re-extracts metadata from the saved output JPEG, and updates `SESSIONS`.
- **`forensic_diff()`**: Calls `compute_forensic_diff()` comparing original vs. modified metadata.
- **`download_file(filename)`** & **`list_cameras()`**: Serves modified JPEGs from `outputs/` and lists available cameras from `CAMERAS_DB`.

### `static/app.js` (Key Frontend Functions)
- **`handleFileUpload(file)`**: Uploads the JPEG to `/api/upload`, stores `sessionId`, renders metadata groups, and populates the camera dropdown.
- **`onCameraSelect(cameraName)`**: Triggered when picking a camera from the dropdown; runs `checkCompatibility()`, calls `/api/get-cascade`, stores `lastAgentCascade`, and reveals the **Preview Cascade** button.
- **`applyCascadeChanges()`**: Stages all 31–39 cascade fields into `stagedChanges` with their proper group (`EXIF` or `Image`).
- **`applyChanges()`**: Sends `stagedChanges` plus `remove_gps` and `remove_makernote` flags to `/api/apply-changes`, re-renders updated metadata, and triggers `runForensicDiff()`.
- **`runAgentForField()`** & **`renderAgentResult()`**: Calls `/api/agent-suggest` and renders the AI analysis, risks, clickable alternatives, and verdict.

