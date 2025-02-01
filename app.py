import os
import json
import googlemaps
from flask import Flask, request, jsonify, render_template, send_from_directory

# Initialize Flask app
app = Flask(__name__)

# Ensure `static/` exists
if not os.path.exists("static"):
    os.makedirs("static")

# Load Google API Key
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

# Store URLs and scraped locations
stored_urls = []
scraped_locations = []

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
    global stored_urls, scraped_locations
    stored_urls = []
    scraped_locations = []
    return jsonify({"message": "URLs and scraped data cleared"}), 200

# 5️⃣ **Start Scraping (Fixed Function)**
@app.route("/start_scraping", methods=["POST"])
def start_scraping():
    global scraped_locations

    # 🔴 Fix: Check if URLs exist before scraping
    if not stored_urls:
        return jsonify({"error": "No URLs to scrape"}), 400

    # 🟢 Mock Data: Simulating real scraping process
    scraped_locations = [
        {"name": "Venue 1", "lat": 40.748817, "lng": -73.985428},  # Empire State
        {"name": "Parking Lot", "lat": 40.748217, "lng": -73.986528}
    ]

    return jsonify({"message": "Scraping completed", "locations": scraped_locations}), 200

# 6️⃣ **Google Geocoding API**
@app.route("/geocode", methods=["GET"])
def geocode():
    address = request.args.get("address")
    if not address:
        return jsonify({"error": "Missing address"}), 400
    result = gmaps.geocode(address)
    return jsonify(result)

# 7️⃣ **Generate & Serve GeoJSON with Polygons**
@app.route("/generate_geojson", methods=["POST"])
def generate_geojson():
    if not scraped_locations:
        return jsonify({"error": "No locations found"}), 400

    # Generate GeoJSON with Polygon Example
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [loc["lng"] - 0.0005, loc["lat"] - 0.0005],  # Bottom-left
                        [loc["lng"] + 0.0005, loc["lat"] - 0.0005],  # Bottom-right
                        [loc["lng"] + 0.0005, loc["lat"] + 0.0005],  # Top-right
                        [loc["lng"] - 0.0005, loc["lat"] + 0.0005],  # Top-left
                        [loc["lng"] - 0.0005, loc["lat"] - 0.0005]   # Closing point
                    ]]
                },
                "properties": {"name": loc["name"]}
            } for loc in scraped_locations
        ]
    }

    # Save GeoJSON
    with open("static/events.geojson", "w") as f:
        json.dump(geojson, f)

    return jsonify({"message": "GeoJSON file created", "file": "/static/events.geojson"}), 200

@app.route("/static/<path:filename>")
def serve_static(filename):
    return send_from_directory("static", filename)

# 8️⃣ **Generate & Serve KML**
@app.route("/generate_kml", methods=["POST"])
def generate_kml():
    if not scraped_locations:
        return jsonify({"error": "No locations found"}), 400

    kml_content = """<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
    <Document>"""

    for loc in scraped_locations:
        kml_content += f"""
        <Placemark>
            <name>{loc['name']}</name>
            <Polygon>
                <outerBoundaryIs>
                    <LinearRing>
                        <coordinates>
                            {loc["lng"] - 0.0005},{loc["lat"] - 0.0005},0
                            {loc["lng"] + 0.0005},{loc["lat"] - 0.0005},0
                            {loc["lng"] + 0.0005},{loc["lat"] + 0.0005},0
                            {loc["lng"] - 0.0005},{loc["lat"] + 0.0005},0
                            {loc["lng"] - 0.0005},{loc["lat"] - 0.0005},0
                        </coordinates>
                    </LinearRing>
                </outerBoundaryIs>
            </Polygon>
        </Placemark>"""

    kml_content += """</Document></kml>"""

    with open("static/events.kml", "w") as f:
        f.write(kml_content)

    return jsonify({"message": "KML file created", "file": "/static/events.kml"}), 200

# 9️⃣ **Run App**
if __name__ == "__main__":
    app.run(debug=True)
