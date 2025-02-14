import os
import json
import requests
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
from flask_cors import CORS

# Initialize Flask app
app = Flask(__name__)
CORS(app)

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")  # Make sure this is set in Heroku ENV variables

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Function to get Place ID from an address
def get_place_id(address):
    url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
    params = {
        "input": address,
        "inputtype": "textquery",
        "fields": "place_id",
        "key": GOOGLE_MAPS_API_KEY,
    }
    response = requests.get(url, params=params).json()
    candidates = response.get("candidates", [])
    return candidates[0]["place_id"] if candidates else None

# Function to get building footprint (polygon) using Place ID
def get_building_footprint(place_id):
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "fields": "geometry",
        "key": GOOGLE_MAPS_API_KEY,
    }
    response = requests.get(url, params=params).json()

    geometry = response.get("result", {}).get("geometry", {})
    location = geometry.get("location", {})

    # Use viewport to generate a simple building footprint
    if "viewport" in geometry:
        bounds = geometry["viewport"]
        footprint = {
            "type": "Polygon",
            "coordinates": [[
                [bounds["southwest"]["lng"], bounds["southwest"]["lat"]],
                [bounds["northeast"]["lng"], bounds["southwest"]["lat"]],
                [bounds["northeast"]["lng"], bounds["northeast"]["lat"]],
                [bounds["southwest"]["lng"], bounds["northeast"]["lat"]],
                [bounds["southwest"]["lng"], bounds["southwest"]["lat"]],
            ]]
        }
    else:
        footprint = {
            "type": "Point",
            "coordinates": [location["lng"], location["lat"]]
        }

    return footprint

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/generate_geojson", methods=["POST"])
def generate_geojson():
    data = request.json
    address = data.get("address")

    if not address:
        return jsonify({"error": "No address provided"}), 400

    place_id = get_place_id(address)
    if not place_id:
        return jsonify({"error": "Place not found"}), 404

    footprint = get_building_footprint(place_id)
    geojson_data = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": footprint,
                "properties": {"address": address}
            }
        ]
    }

    geojson_path = os.path.join(UPLOAD_FOLDER, "building.geojson")
    with open(geojson_path, "w") as geojson_file:
        json.dump(geojson_data, geojson_file)

    return jsonify({"message": "GeoJSON generated", "geojson_file": "building.geojson"}), 200

@app.route("/download_geojson")
def download_geojson():
    geojson_path = os.path.join(UPLOAD_FOLDER, "building.geojson")
    if os.path.exists(geojson_path):
        return send_file(geojson_path, as_attachment=True)
    return jsonify({"message": "GeoJSON file not found"}), 404

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

