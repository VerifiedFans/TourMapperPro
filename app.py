from flask import Flask, render_template, request, jsonify, url_for, send_file
from celery import Celery
import os
import redis
import time
import json
from shapely.geometry import Point, Polygon
import geopandas as gpd
import pandas as pd

app = Flask(__name__)

# Redis Configuration
redis_url = os.environ.get(
    "REDIS_URL", "rediss://:<your-redis-password>@<redis-host>:<port>/0?ssl_cert_reqs=CERT_NONE"
)
app.config['CELERY_BROKER_URL'] = redis_url
app.config['CELERY_RESULT_BACKEND'] = redis_url

# Celery Initialization
def make_celery(app):
    celery = Celery(app.import_name, broker=app.config['CELERY_BROKER_URL'])
    celery.conf.update(app.config)
    return celery

celery = make_celery(app)

# Route: Home Page
@app.route("/")
def index():
    return render_template("index.html")

# Route: Upload CSV File
@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    # Save the uploaded CSV file
    file_path = os.path.join("uploads", file.filename)
    os.makedirs("uploads", exist_ok=True)
    file.save(file_path)

    # Start the background task
    task = process_csv.delay(file_path)
    return jsonify({"task_id": task.id}), 202

# Route: Task Status
@app.route("/task-status/<task_id>")
def task_status(task_id):
    task = celery.AsyncResult(task_id)
    if task.state == "PENDING":
        response = {"state": task.state, "progress": 0}
    elif task.state != "FAILURE":
        response = {
            "state": task.state,
            "progress": task.info.get("progress", 0),
        }
        if task.state == "SUCCESS":
            response["result"] = task.info.get("result", {})
    else:
        response = {"state": task.state, "error": str(task.info)}
    return jsonify(response)

# Route: Download GeoJSON
@app.route("/download/<filename>")
def download(filename):
    return send_file(f"output/{filename}", as_attachment=True)

# Celery Task: Process CSV
@celery.task(bind=True)
def process_csv(self, file_path):
    self.update_state(state="PROGRESS", meta={"progress": 10})

    # Read the CSV file
    data = pd.read_csv(file_path)
    if not {"venue_name", "address", "city", "state", "zip", "date"}.issubset(data.columns):
        raise ValueError("CSV file must contain 'venue_name', 'address', 'city', 'state', 'zip', and 'date' columns.")

    self.update_state(state="PROGRESS", meta={"progress": 30})

    # Generate Polygons (Placeholder Logic)
    features = []
    for _, row in data.iterrows():
        venue_coords = Point(-84.1133, 34.4181)  # Replace with real geocoding logic
        parking_coords = Point(-84.1129, 34.4179)  # Replace with real geocoding logic

        venue_polygon = Polygon([
            (venue_coords.x - 0.001, venue_coords.y - 0.001),
            (venue_coords.x + 0.001, venue_coords.y - 0.001),
            (venue_coords.x + 0.001, venue_coords.y + 0.001),
            (venue_coords.x - 0.001, venue_coords.y + 0.001),
            (venue_coords.x - 0.001, venue_coords.y - 0.001),
        ])

        parking_polygon = Polygon([
            (parking_coords.x - 0.002, parking_coords.y - 0.002),
            (parking_coords.x + 0.002, parking_coords.y - 0.002),
            (parking_coords.x + 0.002, parking_coords.y + 0.002),
            (parking_coords.x - 0.002, parking_coords.y + 0.002),
            (parking_coords.x - 0.002, parking_coords.y - 0.002),
        ])

        # Combine venue and parking polygons
        combined_polygon = venue_polygon.union(parking_polygon)
        features.append({
            "type": "Feature",
            "geometry": json.loads(gpd.GeoSeries([combined_polygon]).to_json())["features"][0]["geometry"],
            "properties": {"name": row["venue_name"]},
        })

    self.update_state(state="PROGRESS", meta={"progress": 70})

    # Save GeoJSON
    output_path = f"output/{os.path.basename(file_path).replace('.csv', '.geojson')}"
    os.makedirs("output", exist_ok=True)
    with open(output_path, "w") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f)

    self.update_state(state="PROGRESS", meta={"progress": 100, "result": {"file_url": url_for("download", filename=os.path.basename(output_path))}})
    return {"file_url": url_for("download", filename=os.path.basename(output_path))}

if __name__ == "__main__":
    app.run(debug=True)
