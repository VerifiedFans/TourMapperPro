from flask import Flask, request, jsonify, send_file, render_template
import csv
import json
import os
import requests
from shapely.geometry import mapping, Polygon

app = Flask(__name__)

GEOJSON_FILE = "polygons.geojson"
API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")  # Google Maps API key

# Store polygons temporarily
collected_polygons = []

@app.route("/")
def index():
    return render_template("index.html", google_maps_api_key=API_KEY)

@app.route("/upload", methods=["POST"])
def upload_csv():
    """Handles CSV file upload"""
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    venue_addresses = []
    parking_addresses = []

    file_data = file.read().decode("utf-8").splitlines()
    csv_reader = csv.reader(file_data)

    for row in csv_reader:
        if len(row) >= 2:  # Ensuring there are enough columns
            venue_addresses.append(row[0])  # First column: venue address
            parking_addresses.append(row[1])  # Second column: parking lot address

    # Convert venue & parking lot addresses into polygons
    venue_polygons = get_polygons_from_addresses(venue_addresses)
    parking_polygons = get_polygons_from_addresses(parking_addresses)

    # Store collected polygons
    collected_polygons.extend(venue_polygons)
    collected_polygons.extend(parking_polygons)

    return jsonify({"status": "completed", "venues": len(venue_polygons), "parking_lots": len(parking_polygons)})


@app.route("/save_polygon", methods=["POST"])
def save_polygon():
    """Stores drawn polygon coordinates"""
    data = request.json
    if not data or "polygon" not in data:
        return jsonify({"error": "Invalid data"}), 400

    collected_polygons.append(Polygon([(p["lng"], p["lat"]) for p in data["polygon"]]))

    return jsonify({"status": "success", "polygon_count": len(collected_polygons)})


@app.route("/download", methods=["GET"])
def download_geojson():
    """Generates and allows download of GeoJSON file"""
    geojson_data = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "geometry": mapping(polygon), "properties": {}} for polygon in collected_polygons
        ]
    }

    with open(GEOJSON_FILE, "w") as f:
        json.dump(geojson_data, f)

    return send_file(GEOJSON_FILE, as_attachment=True)


def get_polygons_from_addresses(addresses):
    """Fetches polygons for venue & parking lot addresses using Google Maps API"""
    polygons = []
    for address in addresses:
        lat, lng = geocode_address(address)
        if lat and lng:
            footprint = create_polygon_around(lat, lng)
            polygons.append(footprint)

    return polygons


def geocode_address(address):
    """Geocodes an address to latitude and longitude"""
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={API_KEY}"
    response = requests.get(url)
    data = response.json()

    if data["status"] == "OK":
        location = data["results"][0]["geometry"]["location"]
        return location["lat"], location["lng"]

    return None, None


def create_polygon_around(lat, lng, size=0.0003):
    """Creates a polygon around a point (venue or parking lot)"""
    return Polygon([
        (lng - size, lat - size),
        (lng + size, lat - size),
        (lng + size, lat + size),
        (lng - size, lat + size),
        (lng - size, lat - size)
    ])


if __name__ == "__main__":
    app.run(debug=True)
