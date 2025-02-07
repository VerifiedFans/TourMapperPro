import os
import json
import time
import pandas as pd
import redis
import requests
from flask import Flask, request, jsonify, send_file, render_template
from werkzeug.utils import secure_filename
from shapely.geometry import mapping, Polygon

# Flask App Setup
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = "/tmp/uploads"
app.config['OUTPUT_FOLDER'] = "/tmp/geojsons"

# Ensure required directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

# Google Maps API Key
GMAPS_API_KEY = os.getenv("GMAPS_API_KEY")
if not GMAPS_API_KEY:
    print("❌ ERROR: Google Maps API Key is missing! Set GMAPS_API_KEY in environment variables.")

# Redis Setup (Handle missing Redis gracefully)
REDIS_URL = os.getenv("REDIS_URL")
cache = None
if REDIS_URL:
    try:
        cache = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        cache.ping()  # Test connection
        print("✅ Redis connected")
    except redis.ConnectionError:
        print("⚠️ Redis connection failed. Running without cache.")
        cache = None


### 📍 Get Coordinates from Google Geocoding API ###
def geocode_address(full_address):
    """Geocodes an address using Google Maps API"""
    if not GMAPS_API_KEY:
        print("❌ Google API Key is missing!")
        return None, None

    # ✅ Check Redis Cache first
    if cache:
        cached_location = cache.get(full_address)
        if cached_location:
            return json.loads(cached_location)

    try:
        geocode_url = f"https://maps.googleapis.com/maps/api/geocode/json?address={full_address}&key={GMAPS_API_KEY}"
        response = requests.get(geocode_url).json()

        if "status" in response and response["status"] == "OVER_QUERY_LIMIT":
            print("🚨 Google API rate limit reached! Try again later.")
            return None, None

        if response['results']:
            lat = response['results'][0]['geometry']['location']['lat']
            lon = response['results'][0]['geometry']['location']['lng']

            # ✅ Store in Redis Cache
            if cache:
                cache.set(full_address, json.dumps([lat, lon]), ex=86400)

            return lat, lon
        else:
            print(f"❌ Geocoding failed for {full_address}: {response}")
            return None, None
    except Exception as e:
        print(f"❌ Geocoding error for {full_address}: {e}")
        return None, None


### 📄 Process CSV and Create GeoJSON ###
def process_csv(csv_file):
    """Reads CSV, geocodes addresses, and generates GeoJSON"""
    df = pd.read_csv(csv_file)

    required_columns = {'venue_name', 'address', 'city', 'state', 'zip', 'date'}
    if not required_columns.issubset(df.columns):
        print("⚠️ Missing required columns in CSV")
        return None

    features = []
    batch_size = 50  # Prevent Google API rate limits

    for index, row in df.iterrows():
        full_address = f"{row['address']}, {row['city']}, {row['state']} {row['zip']}"

        lat, lon = geocode_address(full_address)
        if not lat or not lon:
            print(f"❌ Skipping {full_address} (No coordinates found)")
            continue

        print(f"📍 Geocoded {full_address} → ({lat}, {lon})")

        # Add point feature to GeoJSON
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [lon, lat]
            },
            "properties": {
                "name": row['venue_name'],
                "type": "venue"
            }
        })

        if (index + 1) % batch_size == 0:
            time.sleep(1)  # ✅ Rate limiting

    # ✅ Save GeoJSON File
    geojson_filename = f"venues_{int(time.time())}.geojson"
    geojson_path = os.path.join(app.config['OUTPUT_FOLDER'], geojson_filename)

    geojson_data = {"type": "FeatureCollection", "features": features}
    with open(geojson_path, "w") as f:
        json.dump(geojson_data, f)

    print(f"✅ GeoJSON saved as: {geojson_filename}")
    return geojson_filename


### 🖥 Flask Routes ###

@app.route('/')
def home():
    return render_template("index.html")


@app.route('/upload', methods=['POST'])
def upload_file():
    """Handles CSV uploads, processes them, and generates GeoJSON"""
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    filename = secure_filename(file.filename)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)

    geojson_filename = process_csv(file_path)
    if not geojson_filename:
        return jsonify({"error": "GeoJSON generation failed"}), 500

    return jsonify({"message": "CSV processed successfully!", "geojson": geojson_filename})


@app.route('/download/<filename>', methods=['GET'])
def download_geojson(filename):
    """Allows downloading the generated GeoJSON file"""
    file_path = os.path.join(app.config['OUTPUT_FOLDER'], filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    else:
        return jsonify({"error": "File not found"}), 404


### 🚀 Run the Flask App ###
if __name__ == '__main__':
    app.run(debug=True)
