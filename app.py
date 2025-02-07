import os
import redis
import json
import csv
import time
from flask import Flask, request, jsonify, send_file, render_template
import googlemaps

app = Flask(__name__)

# ✅ Load Environment Variables
GOOGLE_MAPS_API_KEY = os.getenv("GMAPS_API_KEY")
REDIS_URL = os.getenv("REDIS_URL")

# ✅ Initialize Google Maps API
if GOOGLE_MAPS_API_KEY:
    gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)
else:
    gmaps = None
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
