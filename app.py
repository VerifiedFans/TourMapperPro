import os
import csv
import json
import requests
import redis
import googlemaps
from flask import Flask, request, render_template, send_file
from werkzeug.utils import secure_filename

# Flask App Setup
app = Flask(__name__)

# Load Environment Variables
REDIS_URL = os.getenv("REDIS_URL")
GMAPS_API_KEY = os.getenv("GMAPS_API_KEY")

# Redis Client (with SSL enabled)
redis_client = redis.StrictRedis.from_url(REDIS_URL, decode_responses=True, ssl=True)

# Google Maps Client
gmaps = googlemaps.Client(key=GMAPS_API_KEY)

# Allowed Upload Folder
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Allowed Extensions
ALLOWED_EXTENSIONS = {"csv"}

# Function to Check File Extension
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# Function to Geocode Address (Uses Redis Cache)
def geocode_address(address):
    cached_result = redis_client.get(address)
    if cached_result:
        return json.loads(cached_result)

    geocode_result = gmaps.geocode(address)
    if geocode_result:
        location = geocode_result[0]["geometry"]["location"]
        redis_client.setex(address, 86400, json.dumps(location))  # Cache for 24 hours
        return location
    return None

# Function to Get Venue Footprint from OpenStreetMap
def get_venue_footprint(lat, lon):
    query = f"""
    [out:json];
    way(around:50,{lat},{lon})["building"];
    out geom;
    """
    url = "https://overpass-api.de/api/interpreter"
    response = requests.get(url, params={"data": query})

    if response.status_code == 200:
        data = response.json()
        if "elements" in data and data["elements"]:
            footprints = []
            for element in data["elements"]:
                if "geometry" in element:
                    coords = [(node["lon"], node["lat"]) for node in element["geometry"]]
                    footprints.append(coords)
            return footprints
    return None

# Route: Home Page (File Upload Form)
@app.route("/", methods=["GET", "POST"])
def upload_file():
    if request.method == "POST":
        file = request.files["file"]
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(filepath)
            return process_csv(filepath)
    return """
    <!doctype html>
    <html>
    <body>
        <h2>Upload CSV to Generate GeoJSON</h2>
        <form method="post" enctype="multipart/form-data">
            <input type="file" name="file">
            <input type="submit" value="Upload">
        </form>
    </body>
    </html>
    """

# Function to Process CSV & Convert to GeoJSON
def process_csv(filepath):
    geojson_data = {"type": "FeatureCollection", "features": []}
    
    with open(filepath, newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            address = row.get("address")  # Ensure CSV has an "address" column
            if address:
                coords = geocode_address(address)
                if coords:
                    # Get venue footprint
                    footprints = get_venue_footprint(coords["lat"], coords["lng"])

                    if footprints:
                        # Store footprint as a polygon
                        for footprint in footprints:
                            feature = {
                                "type": "Feature",
                                "geometry": {"type": "Polygon", "coordinates": [footprint]},
                                "properties": row
                            }
                            geojson_data["features"].append(feature)
                    else:
                        # Store as a point if no footprint is found
                        feature = {
                            "type": "Feature",
                            "geometry": {"type": "Point", "coordinates": [coords["lng"], coords["lat"]]},
                            "properties": row
                        }
                        geojson_data["features"].append(feature)

    output_filepath = os.path.join(app.config["UPLOAD_FOLDER"], "output.geojson")
    with open(output_filepath, "w", encoding="utf-8") as geojson_file:
        json.dump(geojson_data, geojson_file, indent=4)

    return f'<a href="/download">Download GeoJSON</a>'

# Route: Download GeoJSON File
@app.route("/download")
def download_file():
    output_filepath = os.path.join(app.config["UPLOAD_FOLDER"], "output.geojson")
    return send_file(output_filepath, as_attachment=True)

# Run the App
if __name__ == "__main__":
    app.run(debug=True)
