import os
import redis
import googlemaps
import csv
import json
from flask import Flask, request, jsonify, send_file, render_template

# Load environment variables
REDIS_URL = os.getenv("REDIS_URL")
GOOGLE_MAPS_API_KEY = os.getenv("GMAPS_API_KEY")

app = Flask(__name__)

# ✅ Initialize Redis with error handling
if not REDIS_URL:
    print("❌ No REDIS_URL found! Running without Redis.")
    redis_client = None
else:
    try:
        redis_client = redis.StrictRedis.from_url(REDIS_URL, decode_responses=True, ssl=True)
        redis_client.ping()  # Test connection
        print("✅ Connected to Redis!")
    except redis.ConnectionError:
        print("❌ Redis connection failed. Running without cache.")
        redis_client = None

# ✅ Initialize Google Maps Client
if not GOOGLE_MAPS_API_KEY:
    print("❌ Google API Key is missing!")
    gmaps = None
else:
    gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)
    print("✅ Google Maps API initialized!")

# ✅ Route to render home page
@app.route('/')
def home():
    return """
    <h1>Flask App Running!</h1>
    <p>Upload CSV to generate GeoJSON.</p>
    <form action="/upload" method="post" enctype="multipart/form-data">
        <input type="file" name="file">
        <button type="submit">Upload</button>
    </form>
    """

# ✅ Upload CSV and generate GeoJSON
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return "No file uploaded", 400

    file = request.files['file']
    if file.filename == '':
        return "No selected file", 400

    addresses = []
    geojson_data = {"type": "FeatureCollection", "features": []}

    csv_reader = csv.DictReader(file.read().decode("utf-8").splitlines())

    for row in csv_reader:
        address = row.get("address")  # Ensure your CSV has an "address" column
        if not address:
            continue

        if redis_client:
            cached_coords = redis_client.get(address)
            if cached_coords:
                lat, lng = map(float, cached_coords.split(","))
                print(f"📍 [Cache] {address} → ({lat}, {lng})")
            else:
                lat, lng = geocode_address(address)
                if lat and lng:
                    redis_client.set(address, f"{lat},{lng}")
        else:
            lat, lng = geocode_address(address)

        if lat and lng:
            geojson_data["features"].append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lng, lat]},
                "properties": {"address": address}
            })

    output_filename = "venues.geojson"
    with open(output_filename, "w") as f:
        json.dump(geojson_data, f)

    print(f"✅ GeoJSON saved as: {output_filename}")
    return jsonify({"message": "File processed successfully", "download_url": "/download"})

# ✅ Download the generated GeoJSON file
@app.route('/download', methods=['GET'])
def download_file():
    try:
        return send_file("venues.geojson", as_attachment=True)
    except Exception as e:
        return str(e), 500

# ✅ Geocode address using Google Maps API
def geocode_address(address):
    if not gmaps:
        print(f"❌ Skipping {address} (Google API Key missing)")
        return None, None

    try:
        geocode_result = gmaps.geocode(address)
        if geocode_result:
            location = geocode_result[0]["geometry"]["location"]
            lat, lng = location["lat"], location["lng"]
            print(f"📍 Geocoded {address} → ({lat}, {lng})")
            return lat, lng
        else:
            print(f"❌ Geocoding failed for {address}")
            return None, None
    except Exception as e:
        print(f"⚠️ Error geocoding {address}: {e}")
        return None, None

# ✅ Run the Flask app
if __name__ == '__main__':
    app.run(debug=True)
