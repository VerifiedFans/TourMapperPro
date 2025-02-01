import os
import json
import googlemaps
from flask import Flask, request, jsonify, render_template, send_from_directory

# Initialize Flask app
app = Flask(__name__)

# Ensure `static/` exists for storing files
if not os.path.exists("static"):
    os.makedirs("static")

# Load Google API Key from environment variables
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

# Store URLs in memory
stored_urls = []

# 1️⃣ **Home Page**
@app.route("/")
def home():
    return render_template("index.html")

# 2️⃣ **Upload URLs**
@app.route("/upload_urls", methods=["POST"])
def upload_urls():
    global stored_urls
    data = request.json
    urls = data.get("urls", [])
    if not urls:
        return jsonify({"error": "No URLs provided"}), 400
    stored_urls.extend(urls)
    return jsonify({"message": "URLs uploaded successfully", "urls": stored_urls}), 200

# 3️⃣ **View Stored URLs**
@app.route("/view_urls")
def view_urls():
    return render_template("view_urls.html", urls=stored_urls)

# 4️⃣ **Clear Stored URLs**
@app.route("/clear_urls", methods=["POST"])
def clear_urls():
    global stored_urls
    stored_urls = []
    return jsonify({"message": "URLs cleared"}), 200

# 5️⃣ **Start Scraping (Mock Function)**
@app.route("/start_scraping", methods=["POST"])
def start_scraping():
    return jsonify({"message": "Scraping started"}), 200

# 6️⃣ **Google Places API - Get Place Details**
@app.route("/get_place_details", methods=["GET"])
def get_place_details():
    place_id = request.args.get("place_id")
    if not place_id:
        return jsonify({"error": "Missing place_id"}), 400
    details = gmaps.place(place_id=place_id)
    return jsonify(details)

# 7️⃣ **Google Geocoding API - Get Lat/Lng**
@app.route("/geocode", methods=["GET"])
def geocode():
    address = request.args.get("address")
    if not address:
        return jsonify({"error": "Missing address"}), 400
    result = gmaps.geocode(address)
    return jsonify(result)

# 8️⃣ **Generate & Serve GeoJSON**
@app.route("/generate_geojson", methods=["POST"])
def generate_geojson():
    data = request.json
    features = []

    for location in data.get("locations", []):
        lat, lng = location.get("lat"), location.get("lng")
        if lat and lng:
            feature = {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lng, lat]},
                "properties": {"name": location.get("name", "Unknown")}
            }
            features.append(feature)

    geojson = {"type": "FeatureCollection", "features": features}
    
    with open("static/events.geojson", "w") as f:
        json.dump(geojson, f)
    
    return jsonify({"message": "GeoJSON file created", "file": "/static/events.geojson"}), 200

@app.route("/static/<path:filename>")
def serve_static(filename):
    return send_from_directory("static", filename)

# 9️⃣ **Generate & Serve KML**
@app.route("/generate_kml", methods=["POST"])
def generate_kml():
    data = request.json
    kml_content = """<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
    <Document>"""

    for location in data.get("locations", []):
        lat, lng = location.get("lat"), location.get("lng")
        name = location.get("name", "Unknown")
        if lat and lng:
            kml_content += f"""
            <Placemark>
                <name>{name}</name>
                <Point>
                    <coordinates>{lng},{lat},0</coordinates>
                </Point>
            </Placemark>"""

    kml_content += """</Document></kml>"""

    with open("static/events.kml", "w") as f:
        f.write(kml_content)

    return jsonify({"message": "KML file created", "file": "/static/events.kml"}), 200

# 1️⃣0️⃣ **Run App**
if __name__ == "__main__":
    app.run(debug=True)
