import os
import json
import logging
import requests
from flask import Flask, request, jsonify, send_file
from shapely.geometry import shape, mapping
import geojson

# ✅ Define Flask app FIRST before using routes
app = Flask(__name__)

# Setup logging for debugging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GEOJSON_STORAGE = "data.geojson"
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")  # Make sure this is set in Heroku Config Vars

progress_status = {"progress": 0}  # Track processing progress

def geocode_address(address):
    """ Convert an address to latitude & longitude using Google Maps API. """
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={GOOGLE_MAPS_API_KEY}"
    response = requests.get(url)
    data = response.json()

    if data.get("status") == "OK":
        location = data["results"][0]["geometry"]["location"]
        return location["lat"], location["lng"]
    else:
        logger.error(f"Geocoding failed for {address}: {data}")
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
    
    try:
        response = requests.get(url, params={"data": overpass_query}, timeout=10)
        data = response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching data from Overpass API: {e}")
        return {"type": "FeatureCollection", "features": []}

    features = []
    for element in data.get("elements", []):
        if "nodes" in element:
            coords = []
            for node_id in element["nodes"]:
                node = next((n for n in data["elements"] if n["id"] == node_id), None)
                if node and "lat" in node and "lon" in node:
                    coords.append([node["lon"], node["lat"]])

            # Ensure polygon is closed
            if coords and coords[0] != coords[-1]:
                coords.append(coords[0])

            feature = {
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [coords]},
                "properties": {"type": "building" if "building" in element.get("tags", {}) else "parking"}
            }
            features.append(feature)

    return {"type": "FeatureCollection", "features": features}

@app.route("/")
def home():
    """ ✅ Fix: Added a simple homepage to prevent 404 errors. """
    return "✅ TourMapper Pro is running! Ready to process CSV files."

@app.route("/progress", methods=["GET"])
def check_progress():
    """ ✅ Fix: Properly returns progress status. """
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
    """ ✅ Fix: Allows users to download the latest GeoJSON file. """
    if os.path.exists(GEOJSON_STORAGE):
        return send_file(GEOJSON_STORAGE, as_attachment=True, mimetype="application/json")
    return jsonify({"status": "error", "message": "No GeoJSON file available"}), 404

# ✅ Fix: Ensure Heroku runs the app on the correct port
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
