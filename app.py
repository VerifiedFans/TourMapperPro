
import os
import json
import logging
import requests
from flask import Flask, request, jsonify, send_file, render_template
from werkzeug.utils import secure_filename

# ✅ Define Flask app with template/static folders
app = Flask(__name__, template_folder="templates", static_folder="static")

# Setup logging for debugging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GEOJSON_STORAGE = "data.geojson"
UPLOAD_FOLDER = "/tmp"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

progress_status = {"progress": 0}  # Track processing progress

@app.route("/")
def home():
    """ ✅ Fix: Render the frontend page properly. """
    logger.info("✅ Serving homepage (index.html)")
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload_csv():
    """ ✅ Handles CSV file upload and logs success/failure. """
    if "file" not in request.files:
        logger.error("❌ No file part in request")
        return jsonify({"status": "error", "message": "No file part"}), 400

    file = request.files["file"]
    if file.filename == "":
        logger.error("❌ No file selected")
        return jsonify({"status": "error", "message": "No selected file"}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    logger.info(f"📂 File '{filename}' uploaded successfully!")
    return jsonify({"status": "completed", "message": "File uploaded successfully"})

@app.route("/generate_polygons", methods=["POST"])
def generate_polygons():
    """ ✅ Generate polygons for venue & parking lot and log progress """
    global progress_status
    progress_status["progress"] = 10  

    data = request.json
    logger.info(f"📩 Received data in /generate_polygons: {data}")  # ✅ Log request data

    if not data or "venue_address" not in data:
        logger.error("❌ Missing venue address in request!")
        return jsonify({"status": "error", "message": "Missing venue address"}), 400

    venue_address = data["venue_address"]
    logger.info(f"📍 Geocoding address: {venue_address}")

    lat, lon = geocode_address(venue_address)
    if not lat or not lon:
        logger.error("❌ Failed to geocode address")
        return jsonify({"status": "error", "message": "Could not geocode address"}), 400

    progress_status["progress"] = 50  

    geojson_data = fetch_osm_polygons(lat, lon)
    if not geojson_data["features"]:
        logger.warning("⚠️ No polygons found for this address")

    with open(GEOJSON_STORAGE, "w") as geojson_file:
        json.dump(geojson_data, geojson_file)

    progress_status["progress"] = 100  
    logger.info("✅ Polygons successfully generated and saved!")

    return jsonify({"status": "completed", "message": "Polygons generated", "geojson": geojson_data})

@app.route("/progress", methods=["GET"])
def check_progress():
    return jsonify(progress_status)

@app.route("/download", methods=["GET"])
def download_geojson():
    if os.path.exists(GEOJSON_STORAGE):
        return send_file(GEOJSON_STORAGE, as_attachment=True, mimetype="application/json")
    return jsonify({"status": "error", "message": "No GeoJSON file available"}), 404

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
