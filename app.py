import os
import json
import requests
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename

# ✅ Initialize Flask app
app = Flask(__name__)

# ✅ API Keys (Replace with actual API keys)
GOOGLE_MAPS_API_KEY = "YOUR_GOOGLE_MAPS_API_KEY"

# ✅ Upload Folder
UPLOAD_FOLDER = "uploads"
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# ✅ Route: Serve `index.html`
@app.route("/")
def home():
    return render_template("index.html")

# ✅ Function: Get Latitude & Longitude from Venue Name
def get_lat_lon(venue_url):
    """ Fetch venue location using Google Maps API """
    try:
        venue_name = venue_url.split("/")[-1]  # Extract last part of the URL
        response = requests.get(
            "https://maps.googleapis.com/maps/api/place/findplacefromtext/json",
            params={
                "input": venue_name,
                "inputtype": "textquery",
                "fields": "geometry",
                "key": GOOGLE_MAPS_API_KEY
            }
        )
        data = response.json()
        if "candidates" in data and len(data["candidates"]) > 0:
            location = data["candidates"][0]["geometry"]["location"]
            return location["lat"], location["lng"]
    except Exception as e:
        print(f"Error fetching location for {venue_url}: {e}")
    return None, None  # Default to None if failed

# ✅ Function: Get Venue Footprints & Parking Lot Polygons
def get_venue_polygons(lat, lon):
    """ Fetch venue footprints & parking lots from OpenStreetMap Overpass API """
    overpass_url = "http://overpass-api.de/api/interpreter"
    overpass_query = f"""
        [out:json];
        (
            way(around:500, {lat}, {lon})["building"];
            way(around:500, {lat}, {lon})["amenity"="parking"];
        );
        out geom;
    """
    try:
        response = requests.get(overpass_url, params={"data": overpass_query})
        data = response.json()
        polygons = []
        for element in data.get("elements", []):
            if "geometry" in element:
                polygon_coords = [[node["lon"], node["lat"]] for node in element["geometry"]]
                polygon_coords.append(polygon_coords[0])  # Close the polygon
                polygons.append({
                    "type": "Feature",
                    "geometry": {"type": "Polygon", "coordinates": [polygon_coords]},
                    "properties": {"type": "parking" if "amenity" in element.get("tags", {}) else "venue"}
                })
        return polygons
    except Exception as e:
        print(f"Error fetching polygons: {e}")
    return []

# ✅ Route: Upload URLs & Process GeoJSON
@app.route("/upload_urls", methods=["POST"])
def upload_urls():
    try:
        data = request.json
        urls = data.get("urls", [])
        geojson_data = {"type": "FeatureCollection", "features": []}

        for url in urls:
            lat, lon = get_lat_lon(url)
            if lat and lon:
                geojson_data["features"].extend(get_venue_polygons(lat, lon))

        # Save to file
        geojson_path = os.path.join(app.config["UPLOAD_FOLDER"], "venues.geojson")
        with open(geojson_path, "w") as f:
            json.dump(geojson_data, f, indent=4)

        return jsonify({"message": "GeoJSON file created successfully!", "download": "/download_geojson"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ✅ Route: Download GeoJSON File
@app.route("/download_geojson", methods=["GET"])
def download_geojson():
    geojson_path = os.path.join(app.config["UPLOAD_FOLDER"], "venues.geojson")
    return send_file(geojson_path, as_attachment=True)

# ✅ Run Flask App
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)

