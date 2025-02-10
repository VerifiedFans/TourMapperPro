import os
import json
import logging
import requests
from flask import Flask, request, jsonify, send_file, render_template
from werkzeug.utils import secure_filename

# ✅ Define Flask app with template/static folders
app = Flask(__name__, template_folder="templates", static_folder="static")

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GEOJSON_STORAGE = "data.geojson"
UPLOAD_FOLDER = "/tmp"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

progress_status = {"progress": 0}  # Track processing progress

@app.route("/")
def home():
    """ ✅ Serve the homepage (index.html) """
    logger.info("✅ Serving homepage (index.html)")
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload_csv():
    """ ✅ Handles CSV file upload """
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
    logger.info(f"📩 Received data in /generate_polygons: {data}")

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

def geocode_address(address):
    """ ✅ Convert an address to latitude & longitude using Google API & OpenStreetMap fallback """
    GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

    if GOOGLE_MAPS_API_KEY:
        url = f"https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={GOOGLE_MAPS_API_KEY}"
        try:
            response = requests.get(url, timeout=5)
            data = response.json()
            logger.info(f"📩 Google API Response: {data}")

            if data.get("status") == "OK":
                location = data["results"][0]["geometry"]["location"]
                logger.info(f"✅ Google Geocode Success: {location['lat']}, {location['lng']}")
                return location["lat"], location["lng"]
            else:
                logger.warning(f"⚠️ Google API failed: {data.get('status')} - {data.get('error_message')}")
        except requests.exceptions.RequestException as e:
            logger.warning(f"⚠️ Google API request failed: {e}")

    # ✅ If Google fails, try OpenStreetMap (OSM)
    logger.info("🔄 Trying OpenStreetMap (Nominatim) as backup...")
    try:
        osm_url = f"https://nominatim.openstreetmap.org/search?q={address}&format=json&limit=1"
        response = requests.get(osm_url, headers={"User-Agent": "TourMapperApp"}, timeout=5)
        data = response.json()

        if data:
            lat, lon = float(data[0]["lat"]), float(data[0]["lon"])
            logger.info(f"✅ OSM Geocode Success: {lat}, {lon}")
            return lat, lon
        else:
            logger.error("❌ OpenStreetMap failed to find coordinates")
            return None, None
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ OpenStreetMap request failed: {e}")
        return None, None

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
