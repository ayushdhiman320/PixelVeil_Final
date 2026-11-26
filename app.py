"""PixelVeil Flask server — REST API routes and static frontend serving."""

import os
import uuid
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

from pixelveil.config import UPLOAD_FOLDER, OUTPUT_FOLDER, CAMERAS_DB, SESSIONS
from pixelveil.metadata_extractor import extract_all_metadata, flatten_meta_plain
from pixelveil.compatibility_engine import (
    compute_compatibility_score,
    find_alternative_cameras,
    get_cascade_changes,
)
from pixelveil.ai_agent import call_groq_agent
from pixelveil.forensic_diff import compute_forensic_diff
from pixelveil.metadata_writer import apply_metadata_changes

app = Flask(__name__, static_folder="static")
CORS(app)


@app.route("/")
def serve_index():
    return send_from_directory("static", "index.html")


@app.route("/static/<path:path>")
def serve_static(path):
    return send_from_directory("static", path)


@app.route("/api/upload", methods=["POST"])
def upload_image():
    if "image" not in request.files:
        return jsonify({"error": "No image file provided"}), 400

    file = request.files["image"]
    if not file.filename.lower().endswith((".jpg", ".jpeg")):
        return jsonify({"error": "Only JPEG files supported"}), 400

    session_id = str(uuid.uuid4())
    filename = f"{session_id}_original.jpg"
    save_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(save_path)

    metadata = extract_all_metadata(save_path)

    SESSIONS[session_id] = {
        "original_path": save_path,
        "current_path": save_path,
        "original_meta": metadata,
        "current_meta": metadata,
        "applied_changes": {},
    }

    return jsonify({
        "session_id": session_id,
        "metadata": metadata,
        "camera_db": list(CAMERAS_DB.keys()),
    })


@app.route("/api/check-compatibility", methods=["POST"])
def check_compatibility():
    data = request.json
    session_id = data.get("session_id")
    proposed_changes = data.get("proposed_changes", {})

    if session_id not in SESSIONS:
        return jsonify({"error": "Invalid session"}), 404

    current_meta = SESSIONS[session_id]["current_meta"]
    flat = flatten_meta_plain(current_meta)

    score, issues = compute_compatibility_score(flat, proposed_changes)

    changed_field = list(proposed_changes.keys())[0] if proposed_changes else ""
    new_value = list(proposed_changes.values())[0] if proposed_changes else ""

    alternatives = []
    if changed_field in ("Model", "Make"):
        alternatives = find_alternative_cameras(str(new_value), flat)

    return jsonify({
        "compatibility_score": score,
        "issues": issues,
        "alternatives": alternatives,
        "risk_level": "high" if score < 50 else "medium" if score < 75 else "low",
    })


@app.route("/api/agent-suggest", methods=["POST"])
def agent_suggest():
    data = request.json
    session_id = data.get("session_id")
    field_changed = data.get("field_changed", "")
    old_value = data.get("old_value", "")
    new_value = data.get("new_value", "")

    if session_id not in SESSIONS:
        return jsonify({"error": "Invalid session"}), 404

    current_meta = SESSIONS[session_id]["current_meta"]
    flat = flatten_meta_plain(current_meta)

    key_fields = {
        k: v for k, v in flat.items()
        if any(f in k for f in ["Make", "Model", "Software", "GPS", "MakerNote", "DateTime", "Lens", "ISO", "Flash"])
    }

    score, issues = compute_compatibility_score(flat, {field_changed: new_value})
    agent_result = call_groq_agent(key_fields, field_changed, old_value, new_value, score, issues)

    cascade = {}
    if field_changed in ("Model", "Make"):
        cascade = get_cascade_changes(str(new_value))

    return jsonify({
        "agent_result": agent_result,
        "compatibility_score": score,
        "issues": issues,
        "cascade_changes": cascade,
    })


@app.route("/api/get-cascade", methods=["POST"])
def get_cascade():
    data = request.json
    target_camera = data.get("target_camera", "")
    cascade = get_cascade_changes(target_camera)
    return jsonify({"cascade_changes": cascade})


@app.route("/api/apply-changes", methods=["POST"])
def apply_changes():
    data = request.json
    session_id = data.get("session_id")
    changes = data.get("changes", {})
    remove_gps = data.get("remove_gps", False)
    remove_makernote = data.get("remove_makernote", False)

    if session_id not in SESSIONS:
        return jsonify({"error": "Invalid session"}), 404

    session = SESSIONS[session_id]
    source_path = session["original_path"]

    out_path, out_name = apply_metadata_changes(source_path, changes, remove_gps, remove_makernote)
    new_meta = extract_all_metadata(out_path)

    session["current_path"] = out_path
    session["current_meta"] = new_meta
    session["applied_changes"] = {**session.get("applied_changes", {}), **changes}

    return jsonify({
        "success": True,
        "metadata": new_meta,
        "output_file": out_name,
    })


@app.route("/api/forensic-diff", methods=["POST"])
def forensic_diff():
    data = request.json
    session_id = data.get("session_id")

    if session_id not in SESSIONS:
        return jsonify({"error": "Invalid session"}), 404

    session = SESSIONS[session_id]
    diff = compute_forensic_diff(session["original_meta"], session["current_meta"])
    return jsonify(diff)


@app.route("/api/download/<filename>", methods=["GET"])
def download_file(filename):
    return send_from_directory(OUTPUT_FOLDER, filename, as_attachment=True)


@app.route("/api/cameras", methods=["GET"])
def list_cameras():
    return jsonify({"cameras": list(CAMERAS_DB.keys())})


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8080)
