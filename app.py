import os
import json
import time
import pandas as pd
import googlemaps
import redis
import geojson
import traceback
from flask import Flask, render_template, request, jsonify, send_file
from shapely.geometry import Polygon, mapping
from werkzeug.utils import secure_filename

# ✅ Flask App Setup
app = Flask(__name__)
UPLOAD_FOLDER = "/tmp/uploads"
OUTPUT_FOLDER = "/tmp/geojsons"

# ✅ Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# ✅ Redis Cache Setup (Fixes connection issues)
REDIS_URL = os.getenv("REDIS_URL")

cache = None  # Default to no Redis
if REDIS_URL:
    try:
        cache = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        cache.ping()  # Test Redis connection
        print("✅ Redis connected successfully!")
    except Exception as e:
        print(f"⚠️ Redis connection failed: {e}")
        cache = None
else:
    print("⚠️ No REDIS_URL found. Running without Redis cache.")

# ✅ Google Maps API Key
GMAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "YOUR_API_KEY_HERE")
gmaps = googlemaps.Client(key=GMAPS_API_KEY)

# ✅ Home Page
@app.route('/')
def index():
    return render_template('index.html')

# ✅ File Upload & Processing
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    try:
        filename = secure_filename(file.filename)
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)

        # ✅ Process the CSV file
        geojson_filename = process_csv(file_path)

        if not geojson_filename:
            raise ValueError("GeoJSON generation failed")

        return jsonify({'status': 'completed', 'file': geojson_filename})

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ✅ Process CSV → Convert to GeoJSON
def process_csv(csv_file):
    """Reads CSV, finds lat/lon, creates polygons, and saves GeoJSON"""
    df = pd.read_csv(csv_file)

    required_columns = {'venue_name', 'address', 'city', 'state', 'zip', 'date'}
    if not required_columns.issubset(df.columns):
        print("⚠️ Missing required columns in CSV")
        return None

    features = []
    batch_size = 50  # Batch size for rate limiting
    
    for index, row in df.iterrows():
        full_address = f"{row['address']}, {row['city']}, {row['state']} {row['zip']}"
        lat, lon = None, None

        # ✅ Check Redis Cache
        if cache:
            cached_location = cache.get(full_address)
            if cached_location:
                lat, lon = json.loads(cached_location)
        
        if not lat or not lon:
            try:
                geocode_result = gmaps.geocode(full_address)
                if not geocode_result:
                    print(f"❌ Geocoding failed for {full_address}")
                    continue
                lat = geocode_result[0]['geometry']['location']['lat']
                lon = geocode_result[0]['geometry']['location']['lng']
                if cache:
                    cache.set(full_address, json.dumps([lat, lon]), ex=86400)
                print(f"📍 Geocoded {full_address} → ({lat}, {lon})")
            except Exception as e:
                print(f"❌ Geocoding error for {full_address}: {e}")
                continue

        # ✅ Create Venue Polygon
        venue_poly = Polygon([
            (lon - 0.0005, lat - 0.0005),
            (lon + 0.0005, lat - 0.0005),
            (lon + 0.0005, lat + 0.0005),
            (lon - 0.0005, lat + 0.0005),
            (lon - 0.0005, lat - 0.0005)
        ])

        # ✅ Create Parking Polygon
        parking_poly = Polygon([
            (lon - 0.001, lat - 0.001),
            (lon + 0.001, lat - 0.001),
            (lon + 0.001, lat + 0.001),
            (lon - 0.001, lat + 0.001),
            (lon - 0.001, lat - 0.001)
        ])

        # ✅ Combine venue & parking into GeoJSON Feature
        features.append({
            "type": "Feature",
            "geometry": mapping(venue_poly),
            "properties": {"name": row['venue_name'], "type": "venue"}
        })
        features.append({
            "type": "Feature",
            "geometry": mapping(parking_poly),
            "properties": {"name": row['venue_name'], "type": "parking"}
        })
        
        if (index + 1) % batch_size == 0:
            time.sleep(1)  # ✅ Rate limiting for Google API

    # ✅ Save GeoJSON File
    geojson_filename = f"venues_{int(time.time())}.geojson"
    geojson_path = os.path.join(OUTPUT_FOLDER, geojson_filename)
    
    geojson_data = {"type": "FeatureCollection", "features": features}
    with open(geojson_path, "w") as f:
        json.dump(geojson_data, f)

    print(f"✅ GeoJSON saved as: {geojson_path}")
    return geojson_filename

# ✅ Download GeoJSON File
@app.route('/download')
def download_file():
    try:
        # Get the most recent GeoJSON file
        files = sorted(os.listdir(OUTPUT_FOLDER), reverse=True)
        if not files:
            raise FileNotFoundError("No GeoJSON files found.")
        
        latest_geojson = files[0]
        geojson_path = os.path.join(OUTPUT_FOLDER, latest_geojson)

        print(f"📥 Downloading file: {geojson_path}")
        return send_file(geojson_path, as_attachment=True)
    except Exception as e:
        print(f"❌ Download error: {e}")
        return jsonify({"error": str(e)}), 500

# ✅ Run the App
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Ensure it runs on Heroku
    app.run(debug=True, host="0.0.0.0", port=port)
