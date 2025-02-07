import os
import redis
import googlemaps
import csv
import json
from flask import Flask, request, send_from_directory, render_template
from werkzeug.utils import secure_filename

# Load environment variables
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
GOOGLE_MAPS_API_KEY = os.getenv("GMAPS_API_KEY")

# Ensure API key is set
if not GOOGLE_MAPS_API_KEY:
    raise ValueError("❌ Google Maps API Key is missing! Set GMAPS_API_KEY in Heroku.")

# Connect to Redis
try:
    redis_client = redis.StrictRedis.from_url(REDIS_URL, decode_responses=True, ssl=True)
    redis_client.ping()
    print("✅ Connected to Redis!")
except redis.ConnectionError:
    print("❌ Redis connection failed. Running without cache.")
    redis_client = None

# Initialize Flask & Google Maps
app = Flask(__name__)
gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

# File storage paths
UPLOAD_FOLDER = "/tmp/uploads"
GEOJSON_FOLDER = "/tmp/geojsons"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(GEOJSON_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


# 📌 Home Route
@app.route("/")
def home():
    return """
    <h1>Flask App Running!</h1>
    <p>Upload CSV to generate GeoJSON.</p>
    <form action='/upload' method='post' enctype='multipart/form-data'>
        <input type='file' name='file'>
        <input type='submit' value='Upload'>
    </form>
    """


# 📌 Upload Route
@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("file")
    if not file:
        return "❌ No file uploaded", 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    # Process CSV and generate GeoJSON
    geojson_filename = process_csv(filepath)
    return f"✅ GeoJSON generated: <a href='/download/{geojson_filename}'>Download</a>"


# 📌 Process CSV and Generate GeoJSON
def process_csv(filepath):
    features = []
    with open(filepath, "r") as csv_file:
        reader = csv.reader(csv_file)
        next(reader)  # Skip header

        for row in reader:
            address = row[0]
            try:
                geocode_result = gmaps.geocode(address)
                if geocode_result:
                    lat = geocode_result[0]["geometry"]["location"]["lat"]
                    lng = geocode_result[0]["geometry"]["location"]["lng"]
                    features.append({
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [lng, lat]},
                        "properties": {"address": address},
                    })
                    print(f"📍 Geocoded {address} → ({lat}, {lng})")
                else:
                    print(f"⚠️ No geocode result for {address}")
            except Exception as e:
                print(f"❌ Geocoding failed for {address}: {e}")

    geojson_data = {"type": "FeatureCollection", "features": features}
    geojson_filename = f"venues_{int(os.path.getmtime(filepath))}.geojson"
    geojson_path = os.path.join(GEOJSON_FOLDER, geojson_filename)

    # Save GeoJSON
    with open(geojson_path, "w") as geojson_file:
        json.dump(geojson_data, geojson_file)
    print(f"✅ GeoJSON saved as: {geojson_filename}")

    return geojson_filename


# 📌 Download GeoJSON Route
@app.route("/download/<filename>")
def download(filename):
    filepath = os.path.join(GEOJSON_FOLDER, filename)
    if os.path.exists(filepath):
        return send_from_directory(GEOJSON_FOLDER, filename, as_attachment=True)
    return "❌ File not found", 404


# Run the Flask app
if __name__ == "__main__":
    app.run(debug=True)
