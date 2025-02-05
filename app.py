import os
import csv
import json
import requests
from flask import Flask, request, render_template, jsonify, send_file
from werkzeug.utils import secure_filename
from celery import Celery
from geopy.geocoders import Nominatim
import geojson
from shapely.geometry import Point, Polygon

app = Flask(__name__)

# 🟢 Celery Configuration
app.config['CELERY_BROKER_URL'] = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
app.config['CELERY_RESULT_BACKEND'] = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)

UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"csv"}

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# 🟢 Function to check allowed file extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# 🟢 Celery Task: Process CSV File
@celery.task(bind=True)
def process_csv(self, file_path):
    geolocator = Nominatim(user_agent="geojson_generator")
    features = []

    with open(file_path, newline='', encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            venue_name = row.get("venue_name")
            address = row.get("address")
            city = row.get("city")
            state = row.get("state")
            zip_code = row.get("zip")
            date = row.get("date")

            full_address = f"{address}, {city}, {state}, {zip_code}"
            location = geolocator.geocode(full_address)

            if location:
                lat, lon = location.latitude, location.longitude

                # Create a sample polygon for the venue footprint
                venue_polygon = Polygon([
                    (lon - 0.0002, lat - 0.0002),
                    (lon + 0.0002, lat - 0.0002),
                    (lon + 0.0002, lat + 0.0002),
                    (lon - 0.0002, lat + 0.0002),
                    (lon - 0.0002, lat - 0.0002)
                ])

                # Create a sample polygon for the parking area
                parking_polygon = Polygon([
                    (lon - 0.0005, lat - 0.0005),
                    (lon + 0.0005, lat - 0.0005),
                    (lon + 0.0005, lat + 0.0005),
                    (lon - 0.0005, lat + 0.0005),
                    (lon - 0.0005, lat - 0.0005)
                ])

                # Merge polygons into a MultiPolygon
                feature = geojson.Feature(
                    geometry=venue_polygon,
                    properties={
                        "name": f"{date} {venue_name} {city}, {state}",
                        "address": full_address,
                        "type": "venue"
                    }
                )

                parking_feature = geojson.Feature(
                    geometry=parking_polygon,
                    properties={
                        "name": f"{venue_name} Parking",
                        "address": full_address,
                        "type": "parking"
                    }
                )

                features.append(feature)
                features.append(parking_feature)

    geojson_data = geojson.FeatureCollection(features)

    output_file = file_path.replace(".csv", ".geojson")
    with open(output_file, "w") as f:
        json.dump(geojson_data, f)

    return output_file

# 🟢 Route: Upload File
@app.route("/", methods=["GET", "POST"])
def upload_file():
    if request.method == "POST":
        if "file" not in request.files:
            return jsonify({"error": "No file part"}), 400

        file = request.files["file"]

        if file.filename == "":
            return jsonify({"error": "No selected file"}), 400

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(file_path)

            task = process_csv.apply_async(args=[file_path])

            return jsonify({"task_id": task.id}), 202

    return render_template("index.html")

# 🟢 Route: Check Task Status
@app.route("/task-status/<task_id>")
def task_status(task_id):
    task = process_csv.AsyncResult(task_id)
    if task.state == "PENDING":
        response = {"status": "Processing..."}
    elif task.state == "SUCCESS":
        response = {"status": "Completed", "download_url": f"/download/{task.result}"}
    else:
        response = {"status": "Failed"}
    return jsonify(response)

# 🟢 Route: Download GeoJSON
@app.route("/download/<filename>")
def download_file(filename):
    file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    return send_file(file_path, as_attachment=True)

# 🟢 Start Flask
if __name__ == "__main__":
    app.run(debug=True)
