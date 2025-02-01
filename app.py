import os
import json
import requests
from flask import Flask, request, jsonify, render_template, send_from_directory

app = Flask(__name__)

# Load API Key from environment variable
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

# Store uploaded URLs
uploaded_urls = []


### ✅ ROUTE: Home Page ###
@app.route("/")
def home():
    return render_template("index.html")


### ✅ ROUTE: Upload URLs ###
@app.route("/upload_urls", methods=["POST"])
def upload_urls():
    global uploaded_urls
    data = request.json
    urls = data.get("urls", [])

    if not urls:
        return jsonify({"error": "No URLs provided"}), 400

    uploaded_urls.extend(urls)
    return jsonify({"message": "URLs uploaded successfully!", "urls": uploaded_urls})


### ✅ ROUTE: View Uploaded URLs ###
@app.route("/view_urls", methods=["GET"])
def view_urls():
    return render_template("view_urls.html", urls=uploaded_urls)


### ✅ ROUTE: Clear Uploaded URLs ###
@app.route("/clear_urls", methods=["POST"])
def clear_urls():
    global uploaded_urls
    uploaded_urls = []
    return jsonify({"message": "URLs cleared successfully!"})


### ✅ FUNCTION: Scrape Google Places API ###
def scrape_data():
    """
    Uses Google Places API to find locations, generate GeoJSON & KML.
    """
    if not GOOGLE_MAPS_API_KEY:
        print("❌ ERROR: Missing Google Maps API key.")
        return

    # Example query: Find parking locations near a city
    search_query = "parking near New York"
    url = f"https://maps.googleapis.com/maps/api/place/textsearch/json?query={search_query}&key={GOOGLE_MAPS_API_KEY}"

    response = requests.get(url)
    data = response.json()

    if "results" not in data:
        print("❌ ERROR: No results found in API response.")
        return

    # Prepare GeoJSON structure
    geojson_data = {
        "type": "FeatureCollection",
        "features": []
    }

    # Prepare KML structure
    kml_data = '<?xml version="1.0" encoding="UTF-8"?>\n'
    kml_data += '<kml xmlns="http://www.opengis.net/kml/2.2">\n'
    kml_data += "<Document>\n"

    for place in data["results"]:
        lat = place["geometry"]["location"]["lat"]
        lng = place["geometry"]["location"]["lng"]
        name = place["name"]
        address = place.get("formatted_address", "No address")

        # Add to GeoJSON
        geojson_data["features"].append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [lng, lat]
            },
            "properties": {
                "name": name,
                "address": address,
                "rating": place.get("rating", "No rating")
            }
        })

        # Add to KML
        kml_data += f'<Placemark>\n'
        kml_data += f'  <name>{name}</name>\n'
        kml_data += f'  <description>{address}</description>\n'
        kml_data += f'  <Point>\n'
        kml_data += f'    <coordinates>{lng},{lat},0</coordinates>\n'
        kml_data += f'  </Point>\n'
        kml_data += f'</Placemark>\n'

    kml_data += "</Document>\n"
    kml_data += "</kml>\n"

    # Save GeoJSON
    with open("static/events.geojson", "w") as geojson_file:
        json.dump(geojson_data, geojson_file, indent=2)

    # Save KML
    with open("static/events.kml", "w") as kml_file:
        kml_file.write(kml_data)

    print("✅ Scraping Complete! Files saved: events.geojson & events.kml")


### ✅ ROUTE: Start Scraping ###
@app.route("/start_scraping", methods=["POST"])
def start_scraping():
    scrape_data()
    return jsonify({"message": "Scraping started successfully!"})


### ✅ ROUTE: Serve Static Files (GeoJSON & KML) ###
@app.route("/static/<path:filename>")
def serve_static(filename):
    return send_from_directory("static", filename)


# Run the Flask app
if __name__ == "__main__":
    app.run(debug=True)
