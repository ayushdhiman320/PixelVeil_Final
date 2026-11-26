"""Groq LLM AI agent for autonomous anti-forensic analysis and suggestions."""

import json
from groq import Groq
from .config import CAMERAS_DB, GROQ_API_KEY


def call_groq_agent(session_meta_flat, field_changed, old_value, new_value, compatibility_score, issues):
    """Call Groq AI for autonomous suggestion — enhanced with full camera profiles."""
    if not GROQ_API_KEY:
        return {"error": "No GROQ_API_KEY set"}

    client = Groq(api_key=GROQ_API_KEY)

    camera_db_summary = {}
    for cam_name, profile in CAMERAS_DB.items():
        camera_db_summary[cam_name] = {
            "Make": profile.get("Make"),
            "Model": profile.get("Model"),
            "category": profile.get("category"),
            "has_gps": profile.get("has_gps"),
            "has_makernotes": profile.get("has_makernotes"),
            "MakerNote_size": profile.get("MakerNote_size", 0),
            "FocalLength": profile.get("FocalLength"),
            "FNumber": profile.get("FNumber"),
            "ISOSpeedRatings": profile.get("ISOSpeedRatings"),
            "Flash": profile.get("Flash"),
            "ColorSpace": profile.get("ColorSpace"),
            "sensor_res": f"{profile.get('sensor_w', '?')}x{profile.get('sensor_h', '?')}",
            "similar_to": profile.get("similar_to", []),
            "forensic_notes": profile.get("forensic_notes", ""),
        }

    issues_text = "\n".join(
        [f"- [{i['severity'].upper()}] {i['field']}: {i['issue']}" for i in issues]
    ) if issues else "None detected"

    key_fields = {
        k: v for k, v in session_meta_flat.items() if any(
            f in k for f in [
                "Make", "Model", "Software", "DateTime", "GPS",
                "MakerNote", "ISO", "FocalLength", "FNumber",
                "Flash", "ColorSpace", "ExposureProgram",
                "MeteringMode", "WhiteBalance", "Lens",
            ]
        )
    }

    prompt = f"""You are a digital forensics expert and anti-forensic consultant for PixelVeil.
PixelVeil modifies JPEG EXIF metadata. Your job is to analyze a proposed change and suggest the safest path.

AVAILABLE CAMERA DATABASE (only these cameras are supported — always pick from this list):
{json.dumps(camera_db_summary, indent=2)}

CURRENT IMAGE KEY METADATA:
{json.dumps(key_fields, indent=2)}

USER ACTION: Changed '{field_changed}' from '{old_value}' to '{new_value}'
COMPATIBILITY SCORE: {compatibility_score}/100
DETECTED ISSUES:
{issues_text}

IMPORTANT RULES:
- Only suggest cameras that exist in the AVAILABLE CAMERA DATABASE above
- MakerNote binary blobs are the #1 forensic fingerprint — if target has one, it cannot be faked
- Sensor category mismatch (smartphone vs DSLR) is easily detected by focal length, sensor noise
- All metadata must be internally consistent (Make matches Model, focal length is plausible, etc.)

Respond ONLY in this exact JSON format (no markdown, no extra text):
{{
  "analysis": "2-3 sentence analysis of why the score is {compatibility_score}/100 and what the main risks are",
  "forensic_risks": ["risk 1", "risk 2", "risk 3"],
  "alternatives": [
    {{"camera": "exact camera name from database", "score": 85, "reason": "why this is safer"}},
    {{"camera": "exact camera name from database", "score": 78, "reason": "why this is safer"}},
    {{"camera": "exact camera name from database", "score": 70, "reason": "why this is safer"}}
  ],
  "must_change_fields": {{"FieldName": "value or action", "FieldName2": "value"}},
  "recommendation": "proceed|change_model|abort",
  "recommendation_reason": "one clear sentence explaining the verdict"
}}"""

    raw = ""
    try:
        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": "You are a digital forensics expert. Respond with valid JSON only — no markdown code blocks, no extra text."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=1200,
        )
        raw = response.choices[0].message.content
        if not raw or not raw.strip():
            return {"error": "Empty response from AI model — try again"}
        raw = raw.strip()
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start != -1 and end > start:
            raw = raw[start:end]
        return json.loads(raw)
    except json.JSONDecodeError as e:
        return {"error": f"JSON parse error: {str(e)}", "raw": (raw or "")[:500]}
    except Exception as e:
        return {"error": str(e)}
