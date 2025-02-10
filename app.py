import os
import json
import logging
import redis
import requests
import pandas as pd
from flask import Flask, request, jsonify, send_file, render_template
from werkzeug.utils import secure_filename

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder="templates", static_folder="static")

# Redis setup
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True) if REDIS_URL else None

# File Storage
UPLOAD_FOLDER = "/tmp"
GEOJSON_STORAGE = "data.geojson"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# API Keys
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# --------------- HELPER FUNCTIONS --------------- #

def get_lat_lon_google(address):
    """ Get lat/lon from Google Maps API """
    if not GOOGLE_API_KEY:
        logger.warning("⚠️ Google API Key missing. Skipping Google Geocoding.")
        return None

    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={GOOGLE_API_KEY}"
    response = requests.get(url).json()

    if response.get("status") == "OK":
        location = response["results"][0]["geometry"]["location"]
        return location["lat"], location["lng"]
    return None

def get_lat_lon_osm(address):
    """ Get lat/lon from OpenStreetMap API """
    url = f"https://nominatim.openstreetmap.org/search?q={address}&format=json"
    response = requests.get(url).json()

    if response and len(response) > 0:
        return float(response[0]["lat"]), float(response[0]["lon"])
    return None

def get_lat_lon_geocodexyz(address):
    """ Get lat/lon from Geocode.xyz API """
    url = f"https://geocode.xyz/{address}?json=1"
    response = requests.get(url).json()

    if "latt" in response and "longt" in response:
        return float(response["latt"]), float(response["longt"])
    return None

def get_lat_lon(address):
    """ Try different geocoding services in order """
    lat_lon = get_lat_lon_google(address)
    if lat_lon:
        logger.info(f"✅ Google Geocoding successful: {lat_lon}")
        return lat_lon

    lat_lon = get_lat_lon_osm(address)
    if lat_lon:
        logger.info(f"✅ OSM Geocoding successful: {lat_lon}")
        return lat_lon

    lat_lon = get_lat_lon_geocodexyz(address)
    if lat_lon:
        logger.info(f"✅ Geocode.xyz successful: {lat_lon}")
        return lat_lon

    logger.error(f"❌ Geocoding failed for address: {address}")
    return None

def generate_geojson(venues):
    """ Generate GeoJSON from venue locations """
    features = []
    for venue in venues:
        if "lat" in venue and "lon" in venue:
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [venue["lon"], venue["lat"]]
                },
                "properties": {
                    "name": venue["name"],
                    "address": venue["address"]
                }
            })
    
    geojson_data = {"type": "FeatureCollection", "features": features}
    
    with open(GEOJSON_STORAGE, "w") as geojson_file:
        json.dump(geojson_data, geojson_file)

    return geojson_data

# --------------- ROUTES --------------- #

@app.route("/")
def home():
    """ Serve index.html """
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload_csv():
    """ Handle CSV file upload & geocode venues """
    if "file" not in request.files:
        return jsonify({"status": "error", "message": "No file part"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"status": "error", "message": "No selected file"}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    # Process CSV
    try:
        df = pd.read_csv(filepath)
        required_columns = {"venue name", "address", "city", "state", "zip", "date"}
        if not required_columns.issubset(set(df.columns.str.lower())):
            return jsonify({"status": "error", "message": "CSV missing required columns"}), 400

        venues = []
        for _, row in df.iterrows():
            full_address = f"{row['address']}, {row['city']}, {row['state']} {row['zip']}"
            lat_lon = get_lat_lon(full_address)

            if lat_lon:
                venue_data = {
                    "name": row["venue name"],
                    "address": full_address,
                    "lat": lat_lon[0],
                    "lon": lat_lon[1]
                }
                venues.append(venue_data)

        # Store results
        if redis_client:
            redis_client.set("geojson_data", json.dumps(venues))

        # Generate GeoJSON file
        geojson_data = generate_geojson(venues)

        return jsonify({"status": "completed", "message": "File processed", "geojson": geojson_data})
    
    except Exception as e:
        logger.error(f"❌ Error processing file: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/download", methods=["GET"])
def download_geojson():
    """ Allows users to download the generated GeoJSON file """
    if os.path.exists(GEOJSON_STORAGE):
        return send_file(GEOJSON_STORAGE, as_attachment=True, mimetype="application/json")
    return jsonify({"type": "FeatureCollection", "features": []})

if __name__ == "__main__":
    app.run(debug=True)
