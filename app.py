import os
import csv
import json
import requests
from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
from flask_dropzone import Dropzone
from celery import Celery
from geopy.geocoders import Nominatim
from shapely.geometry import Polygon

# Initialize Flask App
app = Flask(__name__)
CORS(app)
dropzone = Dropzone(app)

# Celery Configuration for Redis
app.config['CELERY_BROKER_URL'] = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
app.config['CELERY_RESULT_BACKEND'] = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')

# Initialize Celery
celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)

UPLOAD_FOLDER = "uploads"
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

geolocator = Nominatim(user_agent="geojson_app")

# Allowed file types
ALLOWED_EXTENSIONS = {"csv"}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# -------------------------- #
#        ROUTES              #
# -------------------------- #

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    if file and allowed_file(file.filename):
        filename = file.filename
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(file_path)

        # Process CSV asynchronously
        task = process_csv.apply_async(args=[file_path])

        return jsonify({"task_id": task.id}), 202

@app.route("/task-status/<task_id>")
def task_status(task_id):
    task = process_csv.AsyncResult(task_id)
    if task.state == "PENDING":
        return jsonify({"status": "Processing"}), 202
    elif task.state == "SUCCESS":
        return jsonify({"status": "Completed", "file_url": f"/download/{task.result}"}), 200
    else:
        return jsonify({"status": "Failed"}), 500

@app.route("/download/<filename>")
def download_file(filename):
    return send_file(os.path.join(app.config["UPLOAD_FOLDER"], filename), as_attachment=True)

# -------------------------- #
#    BACKGROUND TASKS        #
# -------------------------- #

@celery.task(bind=True)
def process_csv(self, file_path):
    """ Reads CSV, gets coordinates, creates polygons, returns GeoJSON """

    venues = []
    
    with open(file_path, "r") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            venue_name = row["venue_name"]
            address = row["address"]
            city = row["city"]
            state = row["state"]
            zip_code = row["zip"]
            date = row["date"]

            full_address = f"{address}, {city}, {state} {zip_code}"
            location = geolocator.geocode(full_address)

            if location:
                lat, lon = location.latitude, location.longitude
                polygon_coords = generate_polygon(lat, lon)
                venues.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [polygon_coords]
                    },
                    "properties": {
                        "name": f"{date} {venue_name} {city} {state}",
                    }
                })

    geojson = {
        "type": "FeatureCollection",
        "features": venues
    }

    output_filename = file_path.replace(".csv", ".geojson")
    with open(output_filename, "w") as geojson_file:
        json.dump(geojson, geojson_file, indent=4)

    return output_filename

# -------------------------- #
#      HELPER FUNCTIONS      #
# -------------------------- #

def generate_polygon(lat, lon):
    """ Generate a square polygon around lat/lon """
    size = 0.001  # Adjust for venue size
    return [
        [lon - size, lat - size, 0],
        [lon + size, lat - size, 0],
        [lon + size, lat + size, 0],
        [lon - size, lat + size, 0],
        [lon - size, lat - size, 0],
    ]

# -------------------------- #
#         RUN APP            #
# -------------------------- #

if __name__ == "__main__":
    app.run(debug=True)
