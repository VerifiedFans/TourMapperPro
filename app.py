
import os
import json
import csv
from flask import Flask, request, render_template, jsonify, send_file
from werkzeug.utils import secure_filename
from celery import Celery
import redis
import boto3

# Initialize Flask app
app = Flask(__name__)

# Set up folders
UPLOAD_FOLDER = "uploads"
RESULTS_FOLDER = "results"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_FOLDER, exist_ok=True)

# Load environment variables
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Celery Configuration (Make sure Redis is set up correctly)
app.config['CELERY_BROKER_URL'] = REDIS_URL
app.config['CELERY_RESULT_BACKEND'] = REDIS_URL  # Fix backend config

# Initialize Celery
celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'], backend=app.config['CELERY_RESULT_BACKEND'])
celery.conf.update(app.config)

# AWS S3 Configuration (Optional)
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")

def upload_to_s3(file_path, s3_key):
    """Upload file to AWS S3"""
    if AWS_ACCESS_KEY and AWS_SECRET_KEY and S3_BUCKET_NAME:
        s3 = boto3.client("s3", aws_access_key_id=AWS_ACCESS_KEY, aws_secret_access_key=AWS_SECRET_KEY)
        s3.upload_file(file_path, S3_BUCKET_NAME, s3_key)
        return f"https://{S3_BUCKET_NAME}.s3.amazonaws.com/{s3_key}"
    return None

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload_file():
    """Handles CSV upload and starts Celery processing"""
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    # Start Celery processing
    task = process_file.delay(filename)
    return jsonify({"task_id": task.id}), 202

@celery.task(bind=True)
def process_file(self, filename):
    """Process CSV and generate GeoJSON"""
    input_path = os.path.join(UPLOAD_FOLDER, filename)
    output_path = os.path.join(RESULTS_FOLDER, f"{filename}.geojson")

    features = []
    total_lines = sum(1 for _ in open(input_path, 'r')) - 1

    with open(input_path, "r") as file:
        reader = csv.DictReader(file)
        for i, row in enumerate(reader, start=1):
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(row["lon"]), float(row["lat"])]
                },
                "properties": {
                    "name": row["venue_name"],
                    "address": row["address"],
                    "city": row["city"],
                    "state": row["state"],
                    "zip": row["zip"],
                    "date": row["date"]
                }
            }
            features.append(feature)

            # Update progress every 10%
            if i % (total_lines // 10 + 1) == 0:
                self.update_state(state="PROGRESS", meta={"progress": int(i / total_lines * 100)})

    # Save GeoJSON
    geojson_data = {"type": "FeatureCollection", "features": features}
    with open(output_path, "w") as f:
        json.dump(geojson_data, f)

    # Upload to S3 (Optional)
    s3_url = upload_to_s3(output_path, f"geojson/{filename}.geojson")

    return {"file_url": s3_url if s3_url else f"/download/{filename}.geojson"}

@app.route("/task-status/<task_id>")
def task_status(task_id):
    """Check Celery task progress"""
    task = process_file.AsyncResult(task_id)
    if task.state == "PENDING":
        return jsonify({"status": "Pending", "progress": 0})
    elif task.state == "PROGRESS":
        return jsonify({"status": "Processing", "progress": task.info.get("progress", 0)})
    elif task.state == "SUCCESS":
        return jsonify({"status": "Completed", "file_url": task.info["file_url"]})
    else:
        return jsonify({"status": "Failed"}), 500

@app.route("/download/<filename>")
def download_file(filename):
    """Download generated GeoJSON file"""
    file_path = os.path.join(RESULTS_FOLDER, filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    return jsonify({"error": "File not found"}), 404

if __name__ == "__main__":
    app.run(debug=True)
