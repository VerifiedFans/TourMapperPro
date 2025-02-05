import os
import json
import pandas as pd
import redis
from flask import Flask, request, render_template, jsonify, send_file
from flask_cors import CORS
from flask_dropzone import Dropzone
from celery import Celery
from geopy.geocoders import Nominatim
from shapely.geometry import Point, Polygon
import numpy as np

app = Flask(__name__)
CORS(app)
dropzone = Dropzone(app)

# 🔹 Load Celery Configuration from Heroku ENV Vars
app.config["CELERY_BROKER_URL"] = os.getenv("REDIS_URL", "redis://localhost:6379/0")
app.config["CELERY_RESULT_BACKEND"] = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery = Celery(app.name, broker=app.config["CELERY_BROKER_URL"])
celery.conf.update(app.config)

# 🔹 Ensure Redis Connection
redis_client = redis.StrictRedis.from_url(app.config["CELERY_BROKER_URL"], decode_responses=True)

# 🔹 Setup Uploads Folder
UPLOAD_FOLDER = "uploads"
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# 🔹 Home Page (Frontend)
@app.route("/")
def index():
    return render_template("index.html")

# 🔹 Background Task: Process CSV & Generate GeoJSON
@celery.task(bind=True)
def process_csv(self, file_path):
    try:
        df = pd.read_csv(file_path)

        if {"venue", "address", "city", "state", "zip", "date"}.issubset(df.columns):
            geolocator = Nominatim(user_agent="geoapiExercises")
            geojson_data = {"type": "FeatureCollection", "features": []}

            for index, row in df.iterrows():
                venue_info = f"{row['address']}, {row['city']}, {row['state']} {row['zip']}"
                location = geolocator.geocode(venue_info)

                if location:
                    # Create a basic rectangle around the venue as a polygon
                    lat, lon = location.latitude, location.longitude
                    offset = 0.001  # ~100m offset

                    polygon_coords = [
                        [lon - offset, lat - offset],
                        [lon + offset, lat - offset],
                        [lon + offset, lat + offset],
                        [lon - offset, lat + offset],
                        [lon - offset, lat - offset],
                    ]

                    feature = {
                        "type": "Feature",
                        "geometry": {"type": "Polygon", "coordinates": [polygon_coords]},
                        "properties": {"name": row["venue"], "date": row["date"]},
                    }

                    geojson_data["features"].append(feature)

                progress = int((index + 1) / len(df) * 100)
                self.update_state(state="PROGRESS", meta={"progress": progress})

            output_file = os.path.join(UPLOAD_FOLDER, "output.geojson")
            with open(output_file, "w") as f:
                json.dump(geojson_data, f)

            return {"status": "SUCCESS", "output_file": output_file}
        else:
            return {"status": "ERROR", "message": "CSV missing required columns"}

    except Exception as e:
        return {"status": "ERROR", "message": str(e)}

# 🔹 File Upload Route
@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"status": "ERROR", "message": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"status": "ERROR", "message": "No selected file"}), 400

    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(file_path)

    task = process_csv.apply_async(args=[file_path])
    return jsonify({"task_id": task.id, "status": "Processing"}), 202

# 🔹 Task Status Route
@app.route("/task-status/<task_id>", methods=["GET"])
def task_status(task_id):
    task = process_csv.AsyncResult(task_id)

    if task.state == "PENDING":
        response = {"status": "PENDING"}
    elif task.state == "PROGRESS":
        response = {"status": "PROGRESS", "progress": task.info.get("progress", 0)}
    elif task.state == "SUCCESS":
        response = {"status": "SUCCESS", "output_file": task.info["output_file"]}
    else:
        response = {"status": "FAILED", "message": str(task.info)}

    return jsonify(response)

# 🔹 Download GeoJSON
@app.route("/download", methods=["GET"])
def download_geojson():
    file_path = os.path.join(UPLOAD_FOLDER, "output.geojson")
    return send_file(file_path, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)
