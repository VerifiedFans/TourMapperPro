import os
import json
import logging
import requests
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
GEOJSON_FILE = "static/events.geojson"

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

logging.basicConfig(level=logging.INFO)

# ✅ Serve the main page
@app.route("/")
def home():
    return render_template("index.html")


# ✅ Upload URL file (TXT or CSV)
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


# ✅ View Uploaded URLs
@app.route("/view_urls", methods=["GET"])
def view_urls():
    files = os.listdir(UPLOAD_FOLDER)
    urls = []
    for file in files:
        file_path = os.path.join(UPLOAD_FOLDER, file)
        with open(file_path, "r") as f:
            urls.extend(f.read().splitlines())

    return jsonify({"urls": urls})


# ✅ Clear Uploaded URLs
@app.route("/clear_urls", methods=["POST"])
def clear_urls():
    for file in os.listdir(UPLOAD_FOLDER):
        os.remove(os.path.join(UPLOAD_FOLDER, file))
    return jsonify({"message": "All uploaded URLs have been cleared"})


# ✅ Helper function: Get venue coordinates
def get_venue_location(venue_name):
    """Fetches latitude and longitude of a venue using OpenStreetMap Overpass API."""
    url = f"https://nominatim.openstreetmap.org/search?q={venue_name}&format=json"
    response = requests.get(url).json()

    if response:
        lat = float(response[0]["lat"])
        lon = float(response[0]["lon"])
        return lat, lon
    return None, None


# ✅ Helper function: Get parking lot polygons
def get_parking_lots(lat, lon):
    """Fetches parking lot polygons near a location using Overpass API."""
    overpass_url = "http://overpass-api.de/api/interpreter"
    query = f"""
    [out:json];
    (
      node["amenity"="parking"](around:500,{lat},{lon});
      way["amenity"="parking"](around:500,{lat},{lon});
      relation["amenity"="parking"](around:500,{lat},{lon});
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


# ✅ Generate and Download GeoJSON
@app.route("/download_geojson", methods=["GET"])
def download_geojson():
    geojson_data = {"type": "FeatureCollection", "features": []}

    # ✅ Read uploaded URLs and extract venues
    files = os.listdir(UPLOAD_FOLDER)
    venues = []
    for file in files:
        file_path = os.path.join(UPLOAD_FOLDER, file)
        with open(file_path, "r") as f:
            venues.extend(f.read().splitlines())

    # ✅ Process each venue
    for venue in venues:
        lat, lon = get_venue_location(venue)
        if lat is None or lon is None:
            continue  # Skip if no location found

        # ✅ Add venue to GeoJSON
        geojson_data["features"].append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {"type": "venue", "name": venue}
        })

        # ✅ Fetch and add parking lots
        parking_lots = get_parking_lots(lat, lon)
        geojson_data["features"].extend(parking_lots)

    # ✅ Save GeoJSON file
    with open(GEOJSON_FILE, "w") as f:
        json.dump(geojson_data, f, indent=4)

    return jsonify({"message": "GeoJSON file generated", "file_url": GEOJSON_FILE})


if __name__ == "__main__":
    app.run(debug=True)

