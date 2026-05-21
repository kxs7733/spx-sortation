"""SPX Sortation proof webapp."""
import logging
import os
import traceback
import uuid
from datetime import datetime, timezone, timedelta

from flask import Flask, jsonify, render_template, request

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("spx")

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
    try:
        driver_id = request.form.get("driver_id", "").strip()
        agency = request.form.get("agency", "").strip()
        mscp_id = request.form.get("mscp_id", "").strip()
        lat_raw = request.form.get("lat", "")
        lon_raw = request.form.get("lon", "")
        photo = request.files.get("photo")

        if not (driver_id and agency and mscp_id and photo and lat_raw and lon_raw):
            return jsonify({"error": "Missing required fields"}), 400

        lat = float(lat_raw)
        lon = float(lon_raw)

        info = reverse_geocode(lat, lon)
        _, distance_m = nearest_mscp(lat, lon)
        distance_m = round(distance_m)
        status = "Review" if distance_m > FAR_THRESHOLD_METERS else "Valid"
        timestamp = datetime.now(SGT).strftime("%Y-%m-%d %H:%M:%S")

        ext = (photo.filename.rsplit(".", 1)[-1] if "." in photo.filename else "jpg").lower()
        fname = f"{driver_id}_{datetime.now(SGT).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.{ext}"
        photo_link = ""
        if DRIVE_FOLDER_ID:
            try:
                photo_link = google_io.upload_photo(
                    DRIVE_FOLDER_ID, fname, photo.read(), photo.mimetype or "image/jpeg"
                )
            except Exception as e:
                log.exception("Drive upload failed")
                return jsonify({"error": f"Drive upload failed: {type(e).__name__}: {e}"}), 500

        try:
            google_io.ensure_header(SHEET_ID, SHEET_HEADERS)
            google_io.append_row(SHEET_ID, [
                driver_id, agency, mscp_id, timestamp, lat, lon,
                (info["address"] + (f" S{info['postal']}" if info["postal"] else "")).strip(),
                distance_m, status, photo_link,
            ])
        except Exception as e:
            log.exception("Sheet append failed")
            return jsonify({"error": f"Sheet append failed: {type(e).__name__}: {e}"}), 500

        return jsonify({"ok": True, "status": status, "distance_m": distance_m})
    except Exception as e:
        log.exception("Submit failed")
        return jsonify({"error": f"{type(e).__name__}: {e}", "trace": traceback.format_exc()[-800:]}), 500


@app.route("/api/debug")
def debug():
    """Diagnose env vars + OneMap auth. Remove once stable."""
    import requests
    out = {
        "SHEET_ID_set": bool(os.environ.get("SHEET_ID")),
        "DRIVE_FOLDER_ID_set": bool(DRIVE_FOLDER_ID),
        "ONEMAP_EMAIL_set": bool(os.environ.get("ONEMAP_EMAIL")),
        "ONEMAP_PASSWORD_set": bool(os.environ.get("ONEMAP_PASSWORD")),
        "GOOGLE_CREDS_inline": bool(os.environ.get("GOOGLE_CREDENTIALS_JSON")),
        "OAUTH_CLIENT_ID_set": bool(os.environ.get("OAUTH_CLIENT_ID")),
        "OAUTH_CLIENT_SECRET_set": bool(os.environ.get("OAUTH_CLIENT_SECRET")),
        "OAUTH_REFRESH_TOKEN_set": bool(os.environ.get("OAUTH_REFRESH_TOKEN")),
    }
    try:
        r = requests.post(
            "https://www.onemap.gov.sg/api/auth/post/getToken",
            json={
                "email": os.environ.get("ONEMAP_EMAIL", ""),
                "password": os.environ.get("ONEMAP_PASSWORD", ""),
            },
            timeout=10,
        )
        out["onemap_status"] = r.status_code
        out["onemap_body"] = r.text[:300]
    except Exception as e:
        out["onemap_error"] = repr(e)
    return jsonify(out)


@app.route("/api/history")
def history():
    driver_id = request.args.get("driver_id", "").strip()
    rows = google_io.read_rows(SHEET_ID, limit=200)
    if driver_id:
        rows = [r for r in rows if r.get("Driver ID") == driver_id]
    return jsonify({"rows": rows})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
