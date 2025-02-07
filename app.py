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


### 📍 Get Venue Footprint using Google Places API ###
def get_venue_footprint(lat, lon):
    """Retrieve venue polygon using Google Places API"""
    try:
        search_url = f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={lat},{lon}&radius=50&type=establishment&key={GMAPS_API_KEY}"
        response = requests.get(search_url).json()

        if "results" in response and response["results"]:
            place_id = response["results"][0]["place_id"]
            details_url = f"https://maps.googleapis.com/maps/api/place/details/json?place_id={place_id}&fields=geometry&key={GMAPS_API_KEY}"
            details_data = requests.get(details_url).json()

            if "result" in details_data and "geometry" in details_data["result"]:
                viewport = details_data["result"]["geometry"]["viewport"]
                return Polygon([
                    (viewport["southwest"]["lng"], viewport["southwest"]["lat"]),
                    (viewport["northeast"]["lng"], viewport["southwest"]["lat"]),
                    (viewport["northeast"]["lng"], viewport["northeast"]["lat"]),
                    (viewport["southwest"]["lng"], viewport["northeast"]["lat"]),
                    (viewport["southwest"]["lng"], viewport["southwest"]["lat"])
                ])
    except Exception as e:
        print(f"❌ Venue footprint error: {e}")
    return None


### 🚗 Get Parking Lot Area using Google Roads API ###
def get_parking_area(lat, lon):
    """Estimate parking area near the venue"""
    try:
        roads_url = f"https://roads.googleapis.com/v1/nearestRoads?points={lat},{lon}&key={GMAPS_API_KEY}"
        data = requests.get(roads_url).json()

        if "snappedPoints" in data and data["snappedPoints"]:
            road_points = [(p["location"]["longitude"], p["location"]["latitude"]) for p in data["snappedPoints"]]
            return Polygon(road_points)
    except Exception as e:
        print(f"❌ Parking area error: {e}")
    return None


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

        # ✅ Check Redis Cache for geolocation
        lat, lon = None, None
        if cache:
            cached_location = cache.get(full_address)
            if cached_location:
                lat, lon = json.loads(cached_location)

        if not lat or not lon:
            try:
                geocode_url = f"https://maps.googleapis.com/maps/api/geocode/json?address={full_address}&key={GMAPS_API_KEY}"
                geocode_result = requests.get(geocode_url).json()
                if not geocode_result['results']:
                    print(f"❌ Geocoding failed for {full_address}")
                    continue
                lat = geocode_result['results'][0]['geometry']['location']['lat']
                lon = geocode_result['results'][0]['geometry']['location']['lng']
                if cache:
                    cache.set(full_address, json.dumps([lat, lon]), ex=86400)
                print(f"📍 Geocoded {full_address} → ({lat}, {lon})")
            except Exception as e:
                print(f"❌ Geocoding error for {full_address}: {e}")
                continue

        # ✅ Get Venue Footprint
        venue_polygon = get_venue_footprint(lat, lon)

        # ✅ Get Parking Lot Polygon
        parking_polygon = get_parking_area(lat, lon)

        # ✅ Save Venue & Parking Polygons
        if venue_polygon:
            features.append({
                "type": "Feature",
                "geometry": mapping(venue_polygon),
                "properties": {"name": row['venue_name'], "type": "venue"}
            })

        if parking_polygon:
            features.append({
                "type": "Feature",
                "geometry": mapping(parking_polygon),
                "properties": {"name": row['venue_name'], "type": "parking"}
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
