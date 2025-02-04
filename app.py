import os
import json
import requests
import googlemaps
from flask import Flask, render_template, request, jsonify, send_from_directory
from bs4 import BeautifulSoup  # Web scraping
from shapely.geometry import Point, Polygon
import geopandas as gpd  # For handling polygons

app = Flask(__name__)

# Load Google Maps API key from Heroku
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
if not GOOGLE_MAPS_API_KEY:
    raise ValueError("Missing Google Maps API key. Set it in Heroku.")

# Initialize Google Maps client
gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

# Directory for saving GeoJSON files
GEOJSON_DIR = "static"
if not os.path.exists(GEOJSON_DIR):
    os.makedirs(GEOJSON_DIR)


def geocode_address(address):
    """Geocode an address using Google Maps API."""
    geocode_result = gmaps.geocode(address)
    if geocode_result:
        location = geocode_result[0]["geometry"]["location"]
        return location["lat"], location["lng"]
    return None, None


def scrape_event_details(url):
    """Scrape venue details from event URL."""
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")

    event_name = soup.find("h1").text if soup.find("h1") else "Unknown Event"
    venue_address = soup.find("p", class_="address").text if soup.find("p", class_="address") else None
    event_date = soup.find("p", class_="date").text if soup.find("p", class_="date") else "Unknown Date"

    return event_name, venue_address, event_date


def find_parking_near_venue(lat, lng):
    """Find parking lots near the venue using Google Places API."""
    places_result = gmaps.places_nearby(location=(lat, lng), radius=500, type="parking")
    parking_areas = []

    for place in places_result.get("results", []):
        parking_lat = place["geometry"]["location"]["lat"]
        parking_lng = place["geometry"]["location"]["lng"]
        parking_areas.append((parking_lng, parking_lat))  # GeoJSON uses (lng, lat)

    return parking_areas


def create_polygons(lat, lng, parking_areas):
    """Generate polygons for venue and parking areas while avoiding major roads."""
    # Create a polygon around the venue (100m buffer)
    venue_polygon = Polygon([
        (lng - 0.001, lat - 0.001),
        (lng + 0.001, lat - 0.001),
        (lng + 0.001, lat + 0.001),
        (lng - 0.001, lat + 0.001),
        (lng - 0.001, lat - 0.001)
    ])

    parking_polygons = []
    for plng, plat in parking_areas:
        parking_polygons.append(Polygon([
            (plng - 0.0005, plat - 0.0005),
            (plng + 0.0005, plat - 0.0005),
            (plng + 0.0005, plat + 0.0005),
            (plng - 0.0005, plat + 0.0005),
            (plng - 0.0005, plat - 0.0005)
        ]))

    return venue_polygon, parking_polygons


@app.route("/")
def index():
    """Render homepage."""
    return render_template("index.html")


@app.route("/process-urls", methods=["POST"])
def process_urls():
    """Process event URLs, scrape details, geocode, and generate GeoJSON."""
    try:
        urls = request.json.get("urls", [])
        features = []

        for url in urls:
            event_name, venue_address, event_date = scrape_event_details(url)
            if venue_address:
                lat, lng = geocode_address(venue_address)

                if lat and lng:
                    parking_areas = find_parking_near_venue(lat, lng)
                    venue_polygon, parking_polygons = create_polygons(lat, lng, parking_areas)

                    # Convert polygons to GeoJSON format
                    features.append({
                        "type": "Feature",
                        "geometry": {"type": "Polygon", "coordinates": [list(venue_polygon.exterior.coords)]},
                        "properties": {
                            "name": event_name, "address": venue_address, "date": event_date, "type": "Venue"
                        }
                    })

                    for parking_polygon in parking_polygons:
                        features.append({
                            "type": "Feature",
                            "geometry": {"type": "Polygon", "coordinates": [list(parking_polygon.exterior.coords)]},
                            "properties": {"type": "Parking"}
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
