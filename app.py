import os
import json
import pandas as pd
import googlemaps
import time
import redis
from flask import Flask, render_template, request, jsonify, send_file
from shapely.geometry import Polygon, mapping
from werkzeug.utils import secure_filename

# ✅ Flask App Setup
app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "geojsons"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
app.config['CACHE'] = redis.Redis(host='localhost', port=6379, db=0)

# ✅ Google Maps API Key (Replace with your actual key)
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
    filename = secure_filename(file.filename)
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(file_path)
    
    # Start processing
    geojson_filename = process_csv(file_path)
    return jsonify({'status': 'completed', 'file': geojson_filename})

def process_csv(csv_file):
    """Reads CSV, finds lat/lon, creates polygons, and saves GeoJSON"""
    df = pd.read_csv(csv_file)

    # Ensure required columns exist
    if not {'venue_name', 'address', 'city', 'state', 'zip', 'date'}.issubset(df.columns):
        return jsonify({'error': 'CSV is missing required columns'}), 400

    features = []
    
    for index, row in df.iterrows():
        full_address = f"{row['address']}, {row['city']}, {row['state']} {row['zip']}"
        cached_location = app.config['CACHE'].get(full_address)
        
        if cached_location:
            lat, lon = json.loads(cached_location)
        else:
            geocode_result = gmaps.geocode(full_address)
            if not geocode_result:
                continue
            lat = geocode_result[0]['geometry']['location']['lat']
            lon = geocode_result[0]['geometry']['location']['lng']
            app.config['CACHE'].set(full_address, json.dumps([lat, lon]), ex=86400)  # Cache for 1 day

        # ✅ Create Venue Polygon (Small square around venue)
        venue_poly = Polygon([
            (lon - 0.0005, lat - 0.0005),
            (lon + 0.0005, lat - 0.0005),
            (lon + 0.0005, lat + 0.0005),
            (lon - 0.0005, lat + 0.0005),
            (lon - 0.0005, lat - 0.0005)
        ])

        # ✅ Create Parking Polygon (Larger square for parking)
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

        time.sleep(1)  # Rate limiting to prevent API overload

    # ✅ Save GeoJSON File
    geojson_data = {"type": "FeatureCollection", "features": features}
    geojson_filename = os.path.join(OUTPUT_FOLDER, "venues.geojson")

    with open(geojson_filename, "w") as f:
        json.dump(geojson_data, f)

    return geojson_filename

# ✅ Download GeoJSON File
@app.route('/download')
def download_file():
    geojson_file = os.path.join(OUTPUT_FOLDER, "venues.geojson")
    return send_file(geojson_file, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)
