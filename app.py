
import os
import redis
import json
import glob
import time
from flask import Flask, request, jsonify, send_file

app = Flask(__name__)

# Load Google Maps API Key
GMAPS_API_KEY = os.getenv("GMAPS_API_KEY")
if not GMAPS_API_KEY:
    print("❌ Google API Key is missing!")
    exit(1)

# Setup Redis Connection with Retry
REDIS_URL = os.getenv("REDIS_URL")
redis_client = None

if REDIS_URL:
    for attempt in range(5):  # Retry up to 5 times
        try:
            redis_client = redis.StrictRedis.from_url(REDIS_URL, decode_responses=True)
            redis_client.ping()
            print("✅ Redis Connected!")
            break
        except redis.exceptions.ConnectionError:
            print(f"⚠️ Redis connection failed. Retrying ({attempt + 1}/5)...")
            time.sleep(2)  # Wait before retrying
    else:
        print("❌ Redis connection failed after 5 attempts. Running without cache.")
        redis_client = None
else:
    print("⚠️ REDIS_URL is not set. Running without cache.")

# Setup Folders
UPLOAD_FOLDER = "/tmp/uploads"
GEOJSON_FOLDER = "/tmp/geojsons"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(GEOJSON_FOLDER, exist_ok=True)

def get_latest_geojson():
    """Fetches the latest GeoJSON file."""
    geojson_files = glob.glob(os.path.join(GEOJSON_FOLDER, "*.geojson"))
    if not geojson_files:
        return None
    return max(geojson_files, key=os.path.getmtime)

# Home Route
@app.route("/", methods=["GET"])
def home():
    return "<h1>Flask App Running!</h1><p>Upload CSV to generate GeoJSON.</p>"

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
        geojson_data.append({"type": "Point", "coordinates": [idx * 0.01, idx * 0.02]})  # Mock coordinates

    # Save GeoJSON
    geojson_filename = f"venues_{int(time.time())}.geojson"
    geojson_path = os.path.join(GEOJSON_FOLDER, geojson_filename)
    with open(geojson_path, "w") as f:
        json.dump({"type": "FeatureCollection", "features": geojson_data}, f)
    
    print(f"✅ GeoJSON saved as: {geojson_path}")

    return jsonify({"success": True, "geojson_file": geojson_filename})

@app.route("/download", methods=["GET"])
def download_geojson():
    """ Serves the most recent GeoJSON file. """
    latest_file = get_latest_geojson()
    
    if not latest_file:
        return jsonify({"error": "No GeoJSON files found"}), 404

    print(f"⬇️ Serving file: {latest_file}")
    return send_file(latest_file, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)
