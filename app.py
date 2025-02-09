import os
import redis
import json
import logging
from flask import Flask, request, jsonify, send_file, render_template

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder="templates", static_folder="static")

# Fetch Redis URL
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")  # Fallback for local testing

# Fix Redis URL Formatting
if not REDIS_URL.startswith(("redis://", "rediss://", "unix://")):
    logger.warning("❌ Invalid Redis URL detected. Check your Heroku config.")
    REDIS_URL = None  # Prevents connection errors

# Connect to Redis (if available)
redis_client = None
if REDIS_URL:
    try:
        redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        redis_client.ping()  # Check Redis connection
        logger.info("✅ Connected to Redis successfully!")
    except redis.exceptions.ConnectionError:
        logger.error("⚠️ Redis connection failed! Running without Redis.")
        redis_client = None  # Prevent crash if Redis fails

# File Storage
GEOJSON_STORAGE = "data.geojson"

@app.route("/")
def home():
    """ Serve index.html """
    return render_template("index.html")  # Fix: Now serves the correct homepage

@app.route("/upload", methods=["POST"])
def upload_csv():
    """ Handles CSV file upload & stores it in Redis """
    if "file" not in request.files:
        return jsonify({"status": "error", "message": "No file part"}), 400
    
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"status": "error", "message": "No selected file"}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join("/tmp", filename)
    file.save(filepath)

    # Simulating parsing and storing in Redis
    try:
        with open(filepath, "r") as f:
            data = f.read()

        if redis_client:
            redis_client.set("uploaded_data", data)
        logger.info(f"📂 File '{filename}' uploaded & stored!")

        return jsonify({"status": "completed", "message": "File uploaded successfully"})
    except Exception as e:
        logger.error(f"❌ Error processing file: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/download", methods=["GET"])
def download_geojson():
    """ Allows users to download the generated GeoJSON file """
    if os.path.exists(GEOJSON_STORAGE):
        return send_file(GEOJSON_STORAGE, as_attachment=True, mimetype="application/json")
    return jsonify({"type": "FeatureCollection", "features": []})

@app.route("/generate_polygons", methods=["POST"])
def generate_polygons():
    """ Generates polygons for venue & parking lots """
    data = request.json
    if not data or "venue_address" not in data:
        return jsonify({"status": "error", "message": "Missing venue address"}), 400

    venue_address = data["venue_address"]
    logger.info(f"🗺️ Generating polygons for venue: {venue_address}")

    # Simulate GeoJSON creation
    geojson_data = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [-74.006, 40.7128], [-74.005, 40.7129], [-74.004, 40.7127], [-74.006, 40.7128]
                    ]]
                },
                "properties": {"name": "Venue Area"}
            }
        ]
    }

    with open(GEOJSON_STORAGE, "w") as geojson_file:
        json.dump(geojson_data, geojson_file)

    if redis_client:
        redis_client.set("geojson_data", json.dumps(geojson_data))
    logger.info("✅ Polygons generated & stored!")

    return jsonify({"status": "completed", "message": "Polygons generated", "geojson": geojson_data})

if __name__ == "__main__":
    app.run(debug=True)
