import os
import json
import logging
import requests
from flask import Flask, request, jsonify, send_file, render_template
from werkzeug.utils import secure_filename

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder="templates", static_folder="static")

GEOJSON_STORAGE = "data.geojson"

# Global progress tracking
progress_status = {"progress": 0}


def geocode_address(address):
    """Uses OpenStreetMap Nominatim API to get latitude and longitude"""
    url = f"https://nominatim.openstreetmap.org/search?q={address}&format=json&limit=1"
    response = requests.get(url).json()
    if response and len(response) > 0:
        lat, lon = float(response[0]["lat"]), float(response[0]["lon"])
        return lat, lon
    return None, None


def fetch_osm_polygons(lat, lon):
    """Fetches building and parking lot polygons using Overpass API"""
    overpass_query = f"""
    [out:json];
    (
        way["building"](around:100,{lat},{lon});
        way["amenity"="parking"](around:100,{lat},{lon});
    );
    out geom;
    """
    response = requests.get("https://overpass-api.de/api/interpreter", params={"data": overpass_query}).json()
    
    geojson_data = {"type": "FeatureCollection", "features": []}

    if "elements" in response:
        for element in response["elements"]:
            if "geometry" in element:
                coordinates = [[(point["lon"], point["lat"]) for point in element["geometry"]]]
                feature = {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": coordinates,
                    },
                    "properties": {"id": element["id"]},
                }
                geojson_data["features"].append(feature)

    return geojson_data


@app.route("/")
def home():
    """Serve the homepage"""
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload_csv():
    """Handles CSV file upload"""
    if "file" not in request.files:
        return jsonify({"status": "error", "message": "No file uploaded"}), 400
    
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"status": "error", "message": "No selected file"}), 400

    filename = secure_filename(file.filename)
    file_path = os.path.join("/tmp", filename)
    file.save(file_path)

    logger.info(f"📂 File '{filename}' uploaded successfully!")
    return jsonify({"status": "completed", "message": "File uploaded successfully"})


@app.route("/generate_polygons", methods=["POST"])
def generate_polygons():
    """Generate polygons for buildings and parking lots"""
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


@app.route("/download", methods=["GET"])
def download_geojson():
    """Allow users to download the generated GeoJSON file"""
    if os.path.exists(GEOJSON_STORAGE):
        return send_file(GEOJSON_STORAGE, as_attachment=True, mimetype="application/json")
    return jsonify({"type": "FeatureCollection", "features": []})


if __name__ == "__main__":
    app.run(debug=True)
