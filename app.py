import os
import json
import logging
import requests
from flask import Flask, request, jsonify, send_file, render_template

# ✅ Define Flask app & ensure it serves HTML
app = Flask(__name__, template_folder="templates", static_folder="static")

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GEOJSON_STORAGE = "data.geojson"
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")  # Ensure this is set in Heroku Config Vars

progress_status = {"progress": 0}  # Track processing progress

@app.route("/")
def home():
    """ ✅ Fix: Render the frontend page instead of plain text. """
    return render_template("index.html")  # ✅ Loads your frontend

@app.route("/progress", methods=["GET"])
def check_progress():
    return jsonify(progress_status)

@app.route("/generate_polygons", methods=["POST"])
def generate_polygons():
    global progress_status
    progress_status["progress"] = 10  

    data = request.json
    if not data or "venue_address" not in data:
        return jsonify({"status": "error", "message": "Missing venue address"}), 400

    venue_address = data["venue_address"]
    lat, lon = geocode_address(venue_address)
    if not lat or not lon:
        return jsonify({"status": "error", "message": "Could not geocode address"}), 400

    progress_status["progress"] = 50  

    geojson_data = fetch_osm_polygons(lat, lon)

    with open(GEOJSON_STORAGE, "w") as geojson_file:
        json.dump(geojson_data, geojson_file)

    progress_status["progress"] = 100  

    return jsonify({"status": "completed", "message": "Polygons generated", "geojson": geojson_data})

@app.route("/download", methods=["GET"])
def download_geojson():
    if os.path.exists(GEOJSON_STORAGE):
        return send_file(GEOJSON_STORAGE, as_attachment=True, mimetype="application/json")
    return jsonify({"status": "error", "message": "No GeoJSON file available"}), 404

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
