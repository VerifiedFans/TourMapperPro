from flask import render_template

@app.route("/")
def home():
    """ Serve the homepage (index.html). """
    return render_template("index.html")
import os
import json
import logging
import requests
from flask import Flask, request, jsonify, send_file
from shapely.geometry import shape, mapping
import geojson

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

GEOJSON_STORAGE = "data.geojson"
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")  # Set in Heroku Config Vars

progress_status = {"progress": 0}  # Track processing progress


def geocode_address(address):
    """ Convert an address to latitude & longitude using Google Maps API. """
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={GOOGLE_MAPS_API_KEY}"
    response = requests.get(url)
    data = response.json()

    if data["status"] == "OK":
        location = data["results"][0]["geometry"]["location"]
        return location["lat"], location["lng"]
    else:
        return None, None


def fetch_osm_polygons(lat, lon):
    """ Fetch building & parking lot polygons from OpenStreetMap using Overpass API. """
    overpass_query = f"""
    [out:json];
    (
        way["building"](around:100,{lat},{lon});
        way["amenity"="parking"](around:100,{lat},{lon});
    );
    out body;
    """
    url = "https://overpass-api.de/api/interpreter"
    response = requests.get(url, params={"data": overpass_query})
    data = response.json()

    features = []
    for element in data["elements"]:
        if "nodes" in element:
            coords = []
            for node_id in element["nodes"]:
                node = next((n for n in data["elements"] if n["id"] == node_id), None)
                if node and "lat" in node and "lon" in node:
                    coords.append([node["lon"], node["lat"]])

            # Close polygon
            if coords and coords[0] != coords[-1]:
                coords.append(coords[0])

            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [coords]
                },
                "properties": {"type": "building" if "building" in element["tags"] else "parking"}
            }
            features.append(feature)

    return {"type": "FeatureCollection", "features": features}


@app.route("/progress", methods=["GET"])
def check_progress():
    """ Check progress of polygon generation. """
    return jsonify(progress_status)


@app.route("/generate_polygons", methods=["POST"])
def generate_polygons():
    """ Generates polygons for venue building & parking lots. """
    global progress_status
    progress_status["progress"] = 10  # Start progress tracking

    data = request.json
    if not data or "venue_address" not in data:
        return jsonify({"status": "error", "message": "Missing venue address"}), 400

    venue_address = data["venue_address"]
    lat, lon = geocode_address(venue_address)
    if not lat or not lon:
        return jsonify({"status": "error", "message": "Could not geocode address"}), 400

    progress_status["progress"] = 50  # Halfway through

    geojson_data = fetch_osm_polygons(lat, lon)

    with open(GEOJSON_STORAGE, "w") as geojson_file:
        json.dump(geojson_data, geojson_file)

    progress_status["progress"] = 100  # Done!

    return jsonify({"status": "completed", "message": "Polygons generated", "geojson": geojson_data})


@app.route("/download", methods=["GET"])
def download_geojson():
    """ Allows users to download the latest generated GeoJSON file. """
    if os.path.exists(GEOJSON_STORAGE):
        return send_file(GEOJSON_STORAGE, as_attachment=True, mimetype="application/json")
    return jsonify({"status": "error", "message": "No GeoJSON file available"}), 404


if __name__ == "__main__":
    app.run(debug=True)
