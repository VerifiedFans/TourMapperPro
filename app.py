import os
import redis
import json
import csv
import time
from flask import Flask, request, jsonify, send_file
import googlemaps

app = Flask(__name__)

# ✅ Load Environment Variables
GOOGLE_MAPS_API_KEY = os.getenv("GMAPS_API_KEY")
REDIS_URL = os.getenv("REDIS_URL")

# ✅ Initialize Google Maps API
gmaps = None
if GOOGLE_MAPS_API_KEY:
    gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)
else:
    print("❌ Google Maps API Key is missing!")

# ✅ Initialize Redis with SSL (Heroku requires `rediss://`)
redis_client = None
if REDIS_URL:
    try:
        redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True, ssl=True)
        redis_client.ping()  # Test connection
        print("✅ Redis Connected Successfully!")
    except redis.ConnectionError:
        print("❌ Redis connection failed. Running without cache.")
        redis_client = None
else:
    print("❌ Redis URL is missing! Running without cache.")

# ✅ Paths
UPLOAD_FOLDER = "/tmp/uploads"
GEOJSON_FOLDER = "/tmp/geojsons"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(GEOJSON_FOLDER, exist_ok=True)

# ✅ Homepage Route
@app.route("/", methods=["GET"])
def home():
    return """Flask App Running!<br>Upload CSV to generate GeoJSON.<br>"""

# ✅ Upload & Process CSV Route
@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    file_path = os.path.join(UPLOAD_FOLDER, "uploaded.csv")
    file.save(file_path)

    venues = process_csv(file_path)
    
    if not venues:
        return jsonify({"error": "No valid addresses in CSV"}), 400

    geojson_file = generate_geojson(venues)
    return jsonify({"message": "GeoJSON generated", "download_url": "/download"}), 200

# ✅ Process CSV File
def process_csv(file_path):
    venues = []
    with open(file_path, newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            address = row.get("Address")
            if address:
                venues.append(geocode_address(address))
    return venues

# ✅ Geocode Address Using Google Maps
def geocode_address(address):
    if not gmaps:
        print(f"❌ Skipping {address} (No Google API Key)")
        return None

    try:
        geocode_result = gmaps.geocode(address)
        if geocode_result:
            lat = geocode_result[0]["geometry"]["location"]["lat"]
            lon = geocode_result[0]["geometry"]["location"]["lng"]
            print(f"📍 Geocoded {address} → ({lat}, {lon})")
            return {"address": address, "lat": lat, "lon": lon}
    except Exception as e:
        print(f"❌ Geocoding failed for {address}: {e}")
    return None

# ✅ Generate GeoJSON
def generate_geojson(venues):
    geojson_data = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [v["lon"], v["lat"]]},
                "properties": {"address": v["address"]}
            }
            for v in venues if v
        ]
    }

    geojson_filename = f"venues_{int(time.time())}.geojson"
    geojson_path = os.path.join(GEOJSON_FOLDER, geojson_filename)

    with open(geojson_path, "w") as f:
        json.dump(geojson_data, f)
    
    print(f"✅ GeoJSON saved as: {geojson_filename}")
    return geojson_filename

# ✅ Download Route (Returns Latest GeoJSON File)
@app.route("/download", methods=["GET"])
def download_geojson():
    try:
        latest_file = sorted(os.listdir(GEOJSON_FOLDER), reverse=True)[0]
        geojson_path = os.path.join(GEOJSON_FOLDER, latest_file)
        return send_file(geojson_path, as_attachment=True)
    except IndexError:
        return jsonify({"error": "No GeoJSON files found"}), 404

if __name__ == "__main__":
    app.run(debug=True)
    
