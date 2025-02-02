import os
import json
import logging
import requests
import threading
import time
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
GEOJSON_FILE = "static/events.geojson"

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

logging.basicConfig(level=logging.INFO)

progress = {"status": "idle", "percent": 0}  # ✅ Track Progress


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(file_path)

    return jsonify({"message": "File uploaded successfully", "filename": file.filename})


@app.route("/view_urls", methods=["GET"])
def view_urls():
    files = os.listdir(UPLOAD_FOLDER)
    urls = []
    for file in files:
        file_path = os.path.join(UPLOAD_FOLDER, file)
        with open(file_path, "r") as f:
            urls.extend(f.read().splitlines())

    return jsonify({"urls": urls})


@app.route("/clear_urls", methods=["POST"])
def clear_urls():
    for file in os.listdir(UPLOAD_FOLDER):
        os.remove(os.path.join(UPLOAD_FOLDER, file))
    return jsonify({"message": "All uploaded URLs have been cleared"})


def get_venue_location(venue_name):
    """Fetch latitude & longitude using OpenStreetMap."""
    url = f"https://nominatim.openstreetmap.org/search?q={venue_name}&format=json"
    response = requests.get(url).json()

    if response:
        lat = float(response[0]["lat"])
        lon = float(response[0]["lon"])
        return lat, lon
    return None, None


def get_parking_lots(lat, lon):
    """Fetch parking lots within 500m using Overpass API."""
    overpass_url = "http://overpass-api.de/api/interpreter"
    query = f"""
    [out:json];
    (
      node["amenity"="parking"](around:500,{lat},{lon});
      way["amenity"="parking"](around:500,{lat},{lon});
    );
    out body;
    >;
    out skel qt;
    """
    response = requests.get(overpass_url, params={"data": query}).json()

    features = []
    for element in response.get("elements", []):
        if element["type"] == "way" and "nodes" in element:
            coordinates = [
                [float(node["lon"]), float(node["lat"])] for node in response["elements"] if node["id"] in element["nodes"]
            ]
            features.append({
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [coordinates]},
                "properties": {"type": "parking"}
            })
    return features


def generate_geojson():
    """Process venues and create a GeoJSON file (with progress tracking)."""
    global progress
    progress["status"] = "processing"
    progress["percent"] = 0

    geojson_data = {"type": "FeatureCollection", "features": []}
    files = os.listdir(UPLOAD_FOLDER)
    venues = []

    for file in files:
        file_path = os.path.join(UPLOAD_FOLDER, file)
        with open(file_path, "r") as f:
            venues.extend(f.read().splitlines())

    total_venues = len(venues)
    if total_venues == 0:
        progress["status"] = "idle"
        return

    # ✅ Process each venue with progress updates
    for i, venue in enumerate(venues):
        lat, lon = get_venue_location(venue)
        if lat is None or lon is None:
            continue

        geojson_data["features"].append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {"type": "venue", "name": venue}
        })

        parking_lots = get_parking_lots(lat, lon)
        geojson_data["features"].extend(parking_lots)

        # ✅ Update Progress
        progress["percent"] = int(((i + 1) / total_venues) * 100)

        time.sleep(0.5)  # Simulating processing time

    # ✅ Save GeoJSON File
    with open(GEOJSON_FILE, "w") as f:
        json.dump(geojson_data, f, indent=4)

    progress["status"] = "complete"


@app.route("/start_processing", methods=["POST"])
def start_processing():
    """Start the GeoJSON creation process in a background thread."""
    threading.Thread(target=generate_geojson).start()
    return jsonify({"message": "Processing started"})


@app.route("/progress", methods=["GET"])
def get_progress():
    """Returns the current processing status and progress %."""
    return jsonify(progress)


@app.route("/download_geojson", methods=["GET"])
def download_geojson():
    """Return the GeoJSON file URL when processing is done."""
    if progress["status"] == "complete":
        return jsonify({"message": "GeoJSON file is ready", "file_url": GEOJSON_FILE})
    else:
        return jsonify({"message": "GeoJSON not ready yet"}), 400


if __name__ == "__main__":
    app.run(debug=True)

