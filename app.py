import os
import json
import time
import requests
import pandas as pd
import redis
from flask import Flask, request, jsonify, send_file, render_template
from flask_cors import CORS
from celery import Celery
from shapely.geometry import Polygon, Point
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

# ✅ Redis & Celery Setup
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL

celery = Celery(app.name, broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND)
celery.conf.update(task_serializer="json", accept_content=["json"], result_serializer="json")

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "output"
ALLOWED_EXTENSIONS = {"csv"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["OUTPUT_FOLDER"] = OUTPUT_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# ✅ Allowed File Types
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# ✅ Geocode Address to Get Latitude & Longitude
def geocode_address(address):
    API_KEY = os.getenv("GEOCODING_API_KEY")  # Add Google Maps or OpenStreetMap API key
    url = f"https://nominatim.openstreetmap.org/search?q={address}&format=json"

    try:
        response = requests.get(url)
        data = response.json()
        if data:
            return {
                "latitude": float(data[0]["lat"]),
                "longitude": float(data[0]["lon"]),
            }
        return {"latitude": None, "longitude": None}
    except Exception as e:
        return {"latitude": None, "longitude": None, "error": str(e)}

# ✅ Generate a Polygon Around the Venue Footprint
def generate_venue_polygon(lat, lon, offset=0.0005):
    return [
        [lon - offset, lat - offset, 0],
        [lon + offset, lat - offset, 0],
        [lon + offset, lat + offset, 0],
        [lon - offset, lat + offset, 0],
        [lon - offset, lat - offset, 0],  # Close the loop
    ]

# ✅ Generate a Polygon for Parking Lot (Offset from Venue)
def generate_parking_polygon(lat, lon, offset=0.001, size=0.0006):
    return [
        [lon - size + offset, lat - size + offset, 0],
        [lon + size + offset, lat - size + offset, 0],
        [lon + size + offset, lat + size + offset, 0],
        [lon - size + offset, lat + size + offset, 0],
        [lon - size + offset, lat - size + offset, 0],  # Close the loop
    ]

# ✅ Celery Task: Process CSV, Geocode Addresses, and Generate GeoJSON
@celery.task(bind=True)
def process_venues(self, filepath):
    df = pd.read_csv(filepath)

    # ✅ Check Required Columns
    required_cols = {"venue_name", "address", "city", "state", "zip", "date"}
    if not required_cols.issubset(df.columns):
        return {"status": "Failed", "error": "Missing required columns"}

    features = []

    # ✅ Process Each Venue
    for index, row in df.iterrows():
        address = f"{row['address']}, {row['city']}, {row['state']} {row['zip']}"
        geo = geocode_address(address)

        if geo["latitude"] and geo["longitude"]:
            venue_polygon = generate_venue_polygon(geo["latitude"], geo["longitude"])
            parking_polygon = generate_parking_polygon(geo["latitude"], geo["longitude"])

            # ✅ Add Venue Polygon
            features.append({
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [venue_polygon]},
                "properties": {
                    "name": f"{row['date']} {row['venue_name']} {row['city']} {row['state']}",
                    "category": "Venue",
                },
            })

            # ✅ Add Parking Polygon
            features.append({
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [parking_polygon]},
                "properties": {
                    "name": f"{row['date']} {row['venue_name']} Parking {row['city']} {row['state']}",
                    "category": "Parking",
                },
            })

        self.update_state(state="PROGRESS", meta={"current": index + 1, "total": len(df)})
        time.sleep(1)

    # ✅ Save to GeoJSON
    geojson_output = os.path.join(OUTPUT_FOLDER, "venues_parking.geojson")
    with open(geojson_output, "w") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f)

    return {"status": "Completed", "geojson_file": geojson_output}

# ✅ Upload CSV File
@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "" or not allowed_file(file.filename):
        return jsonify({"error": "Invalid file type"}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    task = process_venues.apply_async(args=[filepath])
    return jsonify({"task_id": task.id}), 202

# ✅ Check Task Status
@app.route("/task-status/<task_id>")
def task_status(task_id):
    task = process_venues.AsyncResult(task_id)
    return jsonify({"status": task.state, "info": task.info})

# ✅ Download GeoJSON File
@app.route("/download/geojson", methods=["GET"])
def download_geojson():
    return send_file("output/venues_parking.geojson", as_attachment=True)

# ✅ Run Flask App
if __name__ == "__main__":
    app.run(debug=True)
    @app.route("/")
def home():
    return render_template("index.html")  # Make sure "templates/index.html" exists
