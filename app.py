import os
import json
import time
from flask import Flask, request, jsonify, render_template, send_file, redirect, url_for
from flask_cors import CORS
from flask_dropzone import Dropzone
from flask_redis import FlaskRedis
from celery import Celery
import pandas as pd
import geojson
from shapely.geometry import Polygon
from geopy.geocoders import Nominatim

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configure Upload Folder
UPLOAD_FOLDER = "uploads"
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Configure Celery with Redis
app.config["REDIS_URL"] = os.getenv("REDIS_URL", "rediss://your-redis-url:6379/")
app.config["CELERY_BROKER_URL"] = app.config["REDIS_URL"]
app.config["CELERY_RESULT_BACKEND"] = app.config["REDIS_URL"]

# Fix Redis SSL Error
if app.config["REDIS_URL"].startswith("rediss://"):
    app.config["REDIS_URL"] += "?ssl_cert_reqs=CERT_NONE"
    app.config["CELERY_BROKER_URL"] = app.config["REDIS_URL"]
    app.config["CELERY_RESULT_BACKEND"] = app.config["REDIS_URL"]

redis_client = FlaskRedis(app)
celery = Celery(app.name, broker=app.config["CELERY_BROKER_URL"])
celery.conf.update(app.config)

dropzone = Dropzone(app)

# Geolocator for converting addresses to coordinates
geolocator = Nominatim(user_agent="geojson_mapper")

# ----------------------------- #
#          ROUTES               #
# ----------------------------- #

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload_file():
    """Handles CSV file uploads."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    filepath = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
    file.save(filepath)

    # Process file in the background
    task = process_csv.delay(filepath)

    return jsonify({"task_id": task.id}), 202

@app.route("/status/<task_id>")
def task_status(task_id):
    """Checks the status of Celery tasks."""
    task = process_csv.AsyncResult(task_id)
    if task.state == "PENDING":
        response = {"status": "Processing", "progress": 10}
    elif task.state == "SUCCESS":
        response = {"status": "Completed", "progress": 100, "download_url": url_for("download_geojson", filename=task.result)}
    elif task.state == "FAILURE":
        response = {"status": "Failed"}
    else:
        response = {"status": task.state}
    
    return jsonify(response)

@app.route("/download/<filename>")
def download_geojson(filename):
    """Allows users to download the generated GeoJSON file."""
    file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    return send_file(file_path, as_attachment=True)

# ----------------------------- #
#       CELERY TASKS            #
# ----------------------------- #

@celery.task(bind=True)
def process_csv(self, filepath):
    """Processes the uploaded CSV and generates GeoJSON."""
    df = pd.read_csv(filepath)
    
    features = []
    for index, row in df.iterrows():
        venue_address = f"{row['address']}, {row['city']}, {row['state']} {row['zip']}"
        location = geolocator.geocode(venue_address)
        
        if location:
            lat, lon = location.latitude, location.longitude
            polygon = Polygon([
                (lon - 0.001, lat - 0.001),
                (lon + 0.001, lat - 0.001),
                (lon + 0.001, lat + 0.001),
                (lon - 0.001, lat + 0.001),
                (lon - 0.001, lat - 0.001)
            ])
            
            feature = geojson.Feature(
                geometry=polygon,
                properties={"name": row["venue_name"]}
            )
            features.append(feature)

        # Update task progress
        self.update_state(state="PROGRESS", meta={"progress": int((index + 1) / len(df) * 100)})

    geojson_data = geojson.FeatureCollection(features)
    output_file = os.path.join(app.config["UPLOAD_FOLDER"], "venues.geojson")
    
    with open(output_file, "w") as f:
        json.dump(geojson_data, f)

    return "venues.geojson"

# ----------------------------- #
#         MAIN EXECUTION        #
# ----------------------------- #

if __name__ == "__main__":
    app.run(debug=True)
