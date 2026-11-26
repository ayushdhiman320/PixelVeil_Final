# PixelVeil

PixelVeil is a Flask-based JPEG metadata inspection and editing tool. It extracts EXIF, GPS, MakerNote, XMP, thumbnail, and interoperability metadata, evaluates proposed camera identity changes against a built-in camera database, and writes coordinated metadata updates into a new JPEG.

The project includes a browser interface, a REST API, optional Groq AI analysis, compatibility scoring, full camera-profile cascades, and a forensic diff report.

> **Responsible use:** PixelVeil is intended for authorized digital-forensics research, privacy testing, photography education, and controlled demonstrations. Do not use metadata manipulation to misrepresent image provenance or evade forensic investigation.

## Features

- Upload and inspect JPEG metadata in an interactive web interface
- Search and edit EXIF and GPS fields
- Score proposed metadata changes for internal compatibility
- Suggest supported alternative camera profiles
- Apply coordinated camera-field changes as a full cascade
- Strip GPS and MakerNote data
- Generate a field-by-field forensic diff and stealth score
- Download the modified JPEG as a separate output file
- Optionally use Groq AI for contextual forensic analysis

## Technology

- Python 3
- Flask and Flask-CORS
- Pillow
- piexif
- Hachoir
- Groq Python SDK
- HTML, CSS, and JavaScript

## Getting Started

### 1. Create and activate a virtual environment

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows:

```powershell
py -m venv .venv
.venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure the optional Groq AI agent

The application runs without a Groq API key, but AI suggestions are disabled.

Set an environment variable:

Linux/macOS:

```bash
export GROQ_API_KEY="your-api-key"
```

Windows PowerShell:

```powershell
$env:GROQ_API_KEY="your-api-key"
```

Alternatively, create `pixelveil_config.txt` in the project root:

```text
GROQ_API_KEY=your-api-key
```

`pixelveil_config.txt` is ignored by Git.

### 4. Start the server

```bash
python app.py
```

Open <http://localhost:8080>.

On Windows, `start.bat` provides the same launch command.

## Basic Workflow

1. Upload a `.jpg` or `.jpeg` file.
2. Inspect the extracted metadata groups.
3. Stage changes to individual fields or select a supported camera profile.
4. Review the compatibility score and AI recommendations.
5. Apply changes to create a new JPEG.
6. Run the forensic diff and download the modified image.

Uploads and generated images are stored as follows:

- `uploads/` — uploaded originals
- `outputs/` — modified JPEG downloads

## REST API

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Serve the web interface |
| `POST` | `/api/upload` | Upload a JPEG and extract metadata |
| `POST` | `/api/check-compatibility` | Score proposed metadata changes |
| `POST` | `/api/agent-suggest` | Request AI analysis and suggestions |
| `POST` | `/api/get-cascade` | Get fields for a target camera profile |
| `POST` | `/api/apply-changes` | Write staged metadata changes to a JPEG |
| `POST` | `/api/forensic-diff` | Compare original and modified metadata |
| `GET` | `/api/download/<filename>` | Download a modified image |
| `GET` | `/api/cameras` | List supported camera profiles |

Session state is kept in memory and is reset when the Flask process restarts.

## Project Structure

```text
app.py                      Flask application and REST routes
cameras_db.json             Supported camera metadata profiles
pixelveil/
  ai_agent.py               Optional Groq AI integration
  compatibility_engine.py   Compatibility scoring and cascades
  forensic_diff.py          Metadata diff and stealth analysis
  metadata_extractor.py     JPEG metadata extraction
  metadata_writer.py        JPEG EXIF encoding and output writing
  config.py                 Paths, configuration, and session state
static/
  index.html                Web interface
  style.css                 Interface styles
  app.js                    Browser-side API integration
requirements.txt            Python dependencies
start.bat                   Windows launcher
```

## Supported Camera Profiles

Camera profiles are loaded from `cameras_db.json`. The database includes metadata fields such as Make, Model, category, sensor dimensions, GPS support, MakerNote properties, focal length, aperture, ISO, flash, color space, and related forensic notes.

## Limitations

- Only JPEG files with `.jpg` or `.jpeg` extensions are accepted.
- AI-based analysis requires a valid Groq API key and network access.
- Session metadata is not persisted beyond the life of the Flask process.
- Metadata-only changes do not alter pixel content or guarantee forensic undetectability.
- Compatibility scores and stealth scores are heuristic estimates, not proof of authenticity or detection resistance.

## Additional Documentation

See [`pixelveil_complete_guide.md`](pixelveil_complete_guide.md) for the detailed project architecture, metadata format, scoring algorithms, and API data flow.
