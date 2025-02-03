
import os
import json
import requests
from flask import Flask, render_template, request, jsonify, send_from_directory
import googlemaps
from bs4 import BeautifulSoup  # Web scraping

app = Flask(__name__)

# Load Google Maps API key from Heroku environment variables
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
if not GOOGLE_MAPS_API_KEY:
    raise ValueError("Missing Google Maps API key. Set it in Heroku.")

# Initialize Google Maps client
gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

# Directory for saving GeoJSON files
GEOJSON_DIR = "static"
if not os.path.exists(GEOJSON_DIR):
    os.makedirs(GEOJSON_DIR)


@app.route("/")
def index():
    """Render homepage."""
    return render_template("index.html")


@app.route("/scrape-events", methods=["POST"])
def scrape_events():
    """Scrape event URLs, geocode locations, and generate GeoJSON."""
    try:
        urls = request.json.get("urls", [])
        features = []

        for url in urls:
            response = requests.get(url)
            soup = BeautifulSoup(response.text, "html.parser")

            # Extract event name & address (Modify these based on actual HTML structure)
            event_name = soup.find("h1").text if soup.find("h1") else "Unknown Event"
            event_address = soup.find("p", class_="address").text if soup.find("p", class_="address") else None

            if event_address:
                # Geocode address
                geocode_result = gmaps.geocode(event_address)
                if geocode_result:
                    location = geocode_result[0]["geometry"]["location"]
                    lat, lng = location["lat"], location["lng"]

                    # Add to GeoJSON
                    features.append({
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [lng, lat]},
                        "properties": {"name": event_name, "address": event_address, "url": url}
                    })

        # Save to GeoJSON
        geojson_data = {"type": "FeatureCollection", "features": features}
        geojson_filename = f"{GEOJSON_DIR}/events.geojson"
        with open(geojson_filename, "w") as geojson_file:
            json.dump(geojson_data, geojson_file, indent=4)

        return jsonify({"message": "GeoJSON created!", "file": "/static/events.geojson"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/static/<path:filename>")
def static_files(filename):
    """Serve static files like GeoJSON."""
    return send_from_directory(GEOJSON_DIR, filename)


if __name__ == "__main__":
    app.run(debug=True)
