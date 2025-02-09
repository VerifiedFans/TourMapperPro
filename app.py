import os
import json
import requests
import csv
import time
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from redis import Redis

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Allow cross-origin requests

# Configure Redis (For Progress Bar)
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
redis_conn = Redis.from_url(redis_url)

UPLOAD_FOLDER = "uploads"
GEOJSON_FOLDER = "geojsons"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(GEOJSON_FOLDER, exist_ok=True)

# Google Maps API Key (Set in Heroku)
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

def get_polygon_from_google(address, type="establishment"):
    """Fetch venue or parking polygon from Google Maps API"""
    base_url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {"query": address, "key": GOOGLE_MAPS_API_KEY}
    
    response = requests.get(base_url, params=params)
    data = response.json()

    if "results" in data and len(data["results"]) > 0:
        place_id = data["results"][0]["place_id"]
        details_url = "https://maps.googleapis.com/maps/api/place/details/json"
        details_params = {"place_id": place_id, "key": GOOGLE_MAPS_API_KEY, "fields": "geometry"}
        details_response = requests.get(details_url, params=details_params)
        details_data = details_response.json()

        if "result" in details_data and "geometry" in details_data["result"]:
            return details_data["result"]["geometry"]
    
    return None  # Return None if no data found

@app.route("/", methods=["GET"])
def home():
    return "TourMapper Pro API Running!"

@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"status": "failed", "message": "No file part"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"status": "failed", "message": "No selected file"}), 400

    filepath = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(filepath)

    geojson_data = {"type": "FeatureCollection", "features": []}

    try:
        with open(filepath, "r", newline='', encoding="utf-8") as csvfile:
            reader = csv.reader(csvfile)
            headers = next(reader)

            total_rows = sum(1 for _ in reader)
            csvfile.seek(0)
            next(reader)

            for i, row in enumerate(reader, start=1):
                if not row:
                    continue
                
                address = row[0]
                venue_polygon = get_polygon_from_google(address, type="establishment")
                parking_polygon = get_polygon_from_google(f"Parking near {address}", type="parking")

                if venue_polygon:
                    geojson_data["features"].append({
                        "type": "Feature",
                        "properties": {"name": f"Venue {i}", "address": address},
                        "geometry": venue_polygon
                    })

                if parking_polygon:
                    geojson_data["features"].append({
                        "type": "Feature",
                        "properties": {"name": f"Parking {i}", "address": address},
                        "geometry": parking_polygon
                    })

                progress = int((i / total_rows) * 100)
                redis_conn.set("progress", progress)

                time.sleep(0.2)

        geojson_path = os.path.join(GEOJSON_FOLDER, "venues_parking.geojson")
        with open(geojson_path, "w", encoding="utf-8") as geojson_file:
            json.dump(geojson_data, geojson_file, indent=4)

        return jsonify({"status": "completed", "message": "Upload successful!"})

    except Exception as e:
        return jsonify({"status": "failed", "message": f"Error processing file: {str(e)}"}), 500

@app.route("/download", methods=["GET"])
def download_geojson():
    geojson_path = os.path.join(GEOJSON_FOLDER, "venues_parking.geojson")
    if os.path.exists(geojson_path):
        return send_file(geojson_path, as_attachment=True)
    return jsonify({"status": "failed", "message": "No GeoJSON file available"}), 404

if __name__ == "__main__":
    app.run(debug=True)
