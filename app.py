from flask import Flask, render_template, request, jsonify, send_file
import json
import os
import time
import requests
from bs4 import BeautifulSoup
from geopy.geocoders import Nominatim
from shapely.geometry import Polygon, Point
import googlemaps

# Flask App Initialization
app = Flask(__name__)
SAVE_DIR = "static"
os.makedirs(SAVE_DIR, exist_ok=True)

# Setup Geolocation & Google Maps
geolocator = Nominatim(user_agent="tourmapper")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

def scrape_event_data(url):
    """
    Scrapes venue details & finds its coordinates.
    """
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, "html.parser")

        # Extract Venue Details (Modify based on actual structure)
        venue_name = soup.find("h1").text.strip()
        address = soup.find("div", class_="venue-address").text.strip()
        date = "2025-02-04"  # Modify to dynamically extract date if available

        # Geocode the venue address
        location = geolocator.geocode(address)
        if location:
            lat, lon = location.latitude, location.longitude
        else:
            return None  # Skip if geolocation fails

        # Create a polygon around the venue
        venue_polygon = [
            [lon - 0.001, lat - 0.001], [lon - 0.001, lat + 0.001],
            [lon + 0.001, lat + 0.001], [lon + 0.001, lat - 0.001],
            [lon - 0.001, lat - 0.001]
        ]

        venue_feature = {
            "type": "Feature",
            "properties": {"name": venue_name, "address": address, "date": date, "type": "venue"},
            "geometry": {"type": "Polygon", "coordinates": [venue_polygon]}
        }

        # Find nearby parking areas
        parking_features = find_parking_areas(lat, lon)

        return [venue_feature] + parking_features
    except Exception as e:
        return None

def find_parking_areas(lat, lon):
    """
    Finds nearby parking lots and creates polygons around them.
    """
    try:
        results = gmaps.places_nearby(location=(lat, lon), radius=500, type="parking")["results"]
        parking_features = []

        for place in results[:5]:  # Limit to 5 nearby parking lots
            parking_name = place["name"]
            parking_lat = place["geometry"]["location"]["lat"]
            parking_lon = place["geometry"]["location"]["lng"]

            # Create a polygon around the parking lot
            parking_polygon = [
                [parking_lon - 0.0008, parking_lat - 0.0008], [parking_lon - 0.0008, parking_lat + 0.0008],
                [parking_lon + 0.0008, parking_lat + 0.0008], [parking_lon + 0.0008, parking_lat - 0.0008],
                [parking_lon - 0.0008, parking_lat - 0.0008]
            ]

            parking_features.append({
                "type": "Feature",
                "properties": {"name": parking_name, "type": "parking"},
                "geometry": {"type": "Polygon", "coordinates": [parking_polygon]}
            })

        return parking_features
    except Exception as e:
        return []

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/process-urls", methods=["POST"])
def process_urls():
    data = request.get_json()
    urls = data.get("urls", [])

    if not urls:
        return jsonify({"message": "No URLs provided."}), 400

    results = []
    for url in urls:
        time.sleep(1)  # Simulated delay
        features = scrape_event_data(url)
        if features:
            results.extend(features)

    if not results:
        return jsonify({"message": "No valid data extracted"}), 400

    # Save to GeoJSON
    geojson_file = os.path.join(SAVE_DIR, "events.geojson")
    with open(geojson_file, "w") as f:
        json.dump({"type": "FeatureCollection", "features": results}, f, indent=2)

    return jsonify({"message": "Scraping Complete!", "download_url": "/static/events.geojson"})

@app.route("/download")
def download():
    return send_file("static/events.geojson", as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)
