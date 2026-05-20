"""SPX Sortation proof webapp."""
import os
import uuid
from datetime import datetime, timezone, timedelta

from flask import Flask, jsonify, render_template, request

import google_io
from config import AGENCIES, DRIVERS, FAR_THRESHOLD_METERS, MSCPS, SHEET_HEADERS
from geo import nearest_mscp, reverse_geocode

SHEET_ID = os.environ.get("SHEET_ID", "1eLw6DmMzJpsO4BoRvxXkh6tvjM_p_mEWBXfch0iRrM0")
DRIVE_FOLDER_ID = os.environ.get("DRIVE_FOLDER_ID", "")

SGT = timezone(timedelta(hours=8))

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/seed")
def seed():
    return jsonify({
        "drivers": DRIVERS,
        "agencies": AGENCIES,
        "mscps": MSCPS,
        "far_threshold_m": FAR_THRESHOLD_METERS,
    })


@app.route("/api/geocode")
def geocode():
    lat = float(request.args.get("lat"))
    lon = float(request.args.get("lon"))
    info = reverse_geocode(lat, lon)
    m, d = nearest_mscp(lat, lon)
    return jsonify({
        "address": info["address"],
        "postal": info["postal"],
        "nearest_mscp": m,
        "distance_m": round(d),
        "far": d > FAR_THRESHOLD_METERS,
    })


@app.route("/api/submit", methods=["POST"])
def submit():
    driver_id = request.form.get("driver_id", "").strip()
    agency = request.form.get("agency", "").strip()
    mscp_id = request.form.get("mscp_id", "").strip()
    lat = float(request.form.get("lat"))
    lon = float(request.form.get("lon"))
    photo = request.files.get("photo")

    if not (driver_id and agency and mscp_id and photo):
        return jsonify({"error": "Missing required fields"}), 400

    info = reverse_geocode(lat, lon)
    _, distance_m = nearest_mscp(lat, lon)
    distance_m = round(distance_m)
    status = "Review" if distance_m > FAR_THRESHOLD_METERS else "Valid"
    timestamp = datetime.now(SGT).strftime("%Y-%m-%d %H:%M:%S")

    ext = (photo.filename.rsplit(".", 1)[-1] if "." in photo.filename else "jpg").lower()
    fname = f"{driver_id}_{datetime.now(SGT).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.{ext}"
    photo_link = ""
    if DRIVE_FOLDER_ID:
        photo_link = google_io.upload_photo(
            DRIVE_FOLDER_ID, fname, photo.read(), photo.mimetype or "image/jpeg"
        )

    google_io.ensure_header(SHEET_ID, SHEET_HEADERS)
    google_io.append_row(SHEET_ID, [
        driver_id,
        agency,
        mscp_id,
        timestamp,
        lat,
        lon,
        (info["address"] + (f" S{info['postal']}" if info["postal"] else "")).strip(),
        distance_m,
        status,
        photo_link,
    ])

    return jsonify({"ok": True, "status": status, "distance_m": distance_m})


@app.route("/api/history")
def history():
    driver_id = request.args.get("driver_id", "").strip()
    rows = google_io.read_rows(SHEET_ID, limit=200)
    if driver_id:
        rows = [r for r in rows if r.get("Driver ID") == driver_id]
    return jsonify({"rows": rows})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
