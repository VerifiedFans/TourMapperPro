import os
import redis
import json
import glob
from flask import Flask, request, jsonify, send_file
import googlemaps

app = Flask(__name__)

# Load Google Maps API Key
GMAPS_API_KEY = os.getenv("GMAPS_API_KEY")
if not GMAPS_API_KEY:
    print("❌ Google API Key is missing!")
    exit(1)

gmaps = googlemaps.Client(key=GMAPS_API_KEY)

# Configure Redis
try:
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis_client = redis.StrictRedis.from_url(REDIS_URL, decode_responses=True)
    redis_client.ping()
    print("✅ Redis Connected!")
except redis.exceptions.ConnectionError:
    redis_client = None
    print("⚠️ Redis connection failed. Running without cache.")

UPLOAD_FOLDER = "/tmp/uploads"
GEOJSON_FOLDER = "/tmp/geojsons"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(GEOJSON_FOLDER, exist_ok=True)

@app.route("/")
def home():
    return "Flask App Running!"

@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    file_path = os.path.join(UPLOAD_FOLDER, "venues.csv")
    file.save(file_path)
    print(f"✅ CSV Loaded: {file_path}")

    # Process file and generate GeoJSON
    geojson_data = []
    addresses = [
        "1684 Frost Rd, Eva, AL 35621",
        "3044 Old Wilkesboro Rd, Jefferson, NC 28640",
        "500 Howard Baker Jr Blvd., Knoxville, TN 37915"
    ]

    for idx, address in enumerate(addresses, start=1):
        print(f"🔍 Processing address {idx}: {address}")
        try:
            geocode_result = gmaps.geocode(address)
            if geocode_result:
                lat = geocode_result[0]["geometry"]["location"]["lat"]
                lon = geocode_result[0]["geometry"]["location"]["lng"]
                print(f"📍 Geocoded {address} → ({lat}, {lon})")
                geojson_data.append({"type": "Point", "coordinates": [lon, lat]})
            else:
                print(f"❌ Geocoding failed for {address}")
        except Exception as e:
            print(f"❌ Geocoding error for {address}: {e}")

    # Save GeoJSON
    geojson_filename = f"venues_{int(os.path.getmtime(file_path))}.geojson"
    geojson_path = os.path.join(GEOJSON_FOLDER, geojson_filename)
    with open(geojson_path, "w") as f:
        json.dump({"type": "FeatureCollection", "features": geojson_data}, f)
    
    print(f"✅ GeoJSON saved as: {geojson_path}")

    return jsonify({"message": "File processed successfully!", "geojson_file": geojson_filename})

@app.route("/download", methods=["GET"])
def download_geojson():
    """ Serves the most recent GeoJSON file. """
    geojson_files = glob.glob(os.path.join(GEOJSON_FOLDER, "*.geojson"))
    
    if not geojson_files:
        return jsonify({"error": "No GeoJSON files found"}), 404

    latest_file = max(geojson_files, key=os.path.getmtime)
    print(f"⬇️ Serving file: {latest_file}")
    
    return send_file(latest_file, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)
