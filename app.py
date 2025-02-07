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

# ✅ Define the Flask App
app = Flask(__name__)

# ✅ Define Upload & Output Folders (Use /tmp/ for Heroku compatibility)
UPLOAD_FOLDER = "/tmp/uploads"
OUTPUT_FOLDER = "/tmp/geojsons"

# ✅ Create Folders If They Don't Exist
for folder in [UPLOAD_FOLDER, OUTPUT_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# ✅ Redis Cache Setup
try:
    cache = redis.Redis.from_url(os.getenv('REDIS_URL'), decode_responses=True)
except Exception as e:
    print(f"⚠️ Redis connection failed: {e}")
    cache = None

# ✅ Google Maps API Key
GMAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "YOUR_API_KEY_HERE")
gmaps = googlemaps.Client(key=GMAPS_API_KEY)

# ✅ Home Page Route
@app.route('/')
def index():
    return render_template('index.html')

# ✅ File Upload & Processing (Only Accepts .CSV)
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    
    # ✅ Check if a file was selected
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    # ✅ Check if the file is a CSV
    if not file.filename.lower().endswith('.csv'):
        return jsonify({'error': 'Invalid file format. Please upload a .csv file'}), 400

    try:
        # ✅ Create /tmp/uploads directory if it doesn’t exist
        if not os.path.exists(UPLOAD_FOLDER):
            os.makedirs(UPLOAD_FOLDER)

        filename = secure_filename(file.filename)
        file_path = os.path.join(UPLOAD_FOLDER, filename)

        file.save(file_path)  # ✅ Save file to /tmp/uploads

        # ✅ Process the CSV file
        geojson_filename = process_csv(file_path)

        if not geojson_filename:
            raise ValueError("GeoJSON generation failed")

        return jsonify({'status': 'completed', 'file': geojson_filename})

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ✅ Process CSV and Generate GeoJSON
def process_csv(csv_file):
    """Reads CSV, finds lat/lon, creates polygons, and saves GeoJSON"""
    try:
    df = pd.read_csv(csv_file)
    print(f"✅ CSV Loaded: {csv_file}")
except Exception as e:
    print(f"❌ Error loading CSV: {e}")
    return None  # Stops the function if CSV loading fails

    required_columns = {'venue_name', 'address', 'city', 'state', 'zip', 'date'}
    if not required_columns.issubset(df.columns):
        return None

    features = []
    batch_size = 50  # Google API rate limiting

    for index, row in df.iterrows():
        full_address = f"{row['address']}, {row['city']}, {row['state']} {row['zip']}"
        lat, lon = None, None
        print(f"🔍 Processing address {index+1}: {full_address}")  # Debugging

        # ✅ Check Redis cache first
        if cache:
            cached_location = cache.get(full_address)
            if cached_location:
                lat, lon = json.loads(cached_location)
                print(f"✅ Cache hit for {full_address}: ({lat}, {lon})")  # Debugging
        
        # ✅ If not cached, geocode using Google Maps API
        if not lat or not lon:
            try:
                geocode_result = gmaps.geocode(full_address)
                if not geocode_result:
                    print(f"⚠️ No geocode result for: {full_address}")
                    continue  # Skip invalid addresses

                lat = geocode_result[0]['geometry']['location']['lat']
                lon = geocode_result[0]['geometry']['location']['lng']
                print(f"📍 Geocoded {full_address} → ({lat}, {lon})")  # Debugging

                if cache:
                    cache.set(full_address, json.dumps([lat, lon]), ex=86400)  # Cache for 1 day

            except Exception as e:
                print(f"❌ Geocoding error for {full_address}: {e}")
                continue  # Skip errors and move to next address

        # ✅ Create Venue Polygon (Slightly adjusted per venue)
        venue_poly = Polygon([
            (lon - 0.0003, lat - 0.0003),
            (lon + 0.0003, lat - 0.0003),
            (lon + 0.0003, lat + 0.0003),
            (lon - 0.0003, lat + 0.0003),
            (lon - 0.0003, lat - 0.0003)
        ])

        # ✅ Create Parking Polygon (Offset from venue)
        parking_poly = Polygon([
            (lon - 0.0006, lat - 0.0006),
            (lon + 0.0006, lat - 0.0006),
            (lon + 0.0006, lat + 0.0006),
            (lon - 0.0006, lat + 0.0006),
            (lon - 0.0006, lat - 0.0006)
        ])

        # ✅ Add venue & parking polygons to GeoJSON
        features.append({
            "type": "Feature",
            "geometry": mapping(venue_poly),
            "properties": {"name": row['venue_name'], "type": "venue", "address": full_address}
        })
        features.append({
            "type": "Feature",
            "geometry": mapping(parking_poly),
            "properties": {"name": row['venue_name'], "type": "parking", "address": full_address}
        })

        if (index + 1) % batch_size == 0:
            time.sleep(1)  # ✅ Prevents Google API rate limit errors

    # ✅ Save GeoJSON File
    geojson_data = {"type": "FeatureCollection", "features": features}
    geojson_filename = os.path.join(OUTPUT_FOLDER, f"venues_{int(time.time())}.geojson")
    
    with open(geojson_filename, "w") as f:
        json.dump(geojson_data, f)

    print(f"✅ GeoJSON saved as: {geojson_filename}")
    return geojson_filename

# ✅ Download GeoJSON File
@app.route('/download')
def download_file():
    geojson_file = os.path.join(OUTPUT_FOLDER, "venues.geojson")
    return send_file(geojson_file, as_attachment=True)

# ✅ Run Flask App (Required for Heroku)
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Ensure it runs on Heroku
    app.run(debug=True, host="0.0.0.0", port=port)
