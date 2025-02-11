import os
import json
import requests
import logging
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, Polygon
from flask import Flask, request, jsonify, send_file, render_template
from bs4 import BeautifulSoup
from geopy.geocoders import Nominatim

# Initialize Flask app
app = Flask(__name__)

# File storage
GEOJSON_STORAGE = "data.geojson"

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ----------------- SCRAPING ARTIST EVENTS ----------------- #

def scrape_past_events(artist_url):
    """Scrapes past event details for 2024 from the artist's event page."""
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(artist_url, headers=headers)

    if response.status_code != 200:
        return {"error": "Failed to fetch artist page"}

    soup = BeautifulSoup(response.text, "html.parser")
    
    events = []
    event_containers = soup.find_all("div", class_="event-card")  # Adjust selector based on the website structure

    for event in event_containers:
        date = event.find("div", class_="event-date").text.strip()
        
        if "2024" in date:
            venue_name = event.find("div", class_="venue-name").text.strip()
            address = event.find("div", class_="venue-address").text.strip()
            city = event.find("div", class_="venue-city").text.strip()
            state = event.find("div", class_="venue-state").text.strip()
            zip_code = event.find("div", class_="venue-zip").text.strip()
            event_url = event.find("a", class_="event-link")["href"]

            events.append({
                "venue_name": venue_name,
                "address": address,
                "city": city,
                "state": state,
                "zip": zip_code,
                "date": date,
                "event_url": event_url
            })

    return events

# ----------------- GEOCODING FUNCTION ----------------- #

def get_lat_lon(address):
    """Gets latitude and longitude of an address using OpenStreetMap API."""
    geolocator = Nominatim(user_agent="tourmapper")
    location = geolocator.geocode(address)
    if location:
        return location.latitude, location.longitude
    return None

# ----------------- GENERATING GEOJSON POLYGONS ----------------- #

def generate_venue_polygon(lat, lon):
    """Generates a polygon around the venue and parking lot."""
    buffer_distance = 0.001  # Approx 100 meters

    point = Point(lon, lat)
    polygon = point.buffer(buffer_distance)  # Creates a circular buffer

    return polygon

def create_geojson(venues):
    """Converts venue data into GeoJSON format."""
    features = []

    for venue in venues:
        lat, lon = venue.get("lat"), venue.get("lon")
        if lat and lon:
            polygon = generate_venue_polygon(lat, lon)
            
            features.append({
                "type": "Feature",
                "geometry": json.loads(gpd.GeoSeries([polygon]).to_json())["features"][0]["geometry"],
                "properties": {
                    "name": venue["venue_name"],
                    "address": venue["address"],
                    "date": venue["date"]
                }
            })

    geojson_data = {"type": "FeatureCollection", "features": features}

    with open(GEOJSON_STORAGE, "w") as geojson_file:
        json.dump(geojson_data, geojson_file)

    return geojson_data

# ----------------- FLASK ROUTES ----------------- #

@app.route("/")
def home():
    """Render the home page."""
    return render_template("index.html")

@app.route("/scrape_events", methods=["POST"])
def scrape_events():
    """Scrapes artist event page and generates GeoJSON."""
    data = request.json
    artist_url = data.get("artist_url")

    if not artist_url:
        return jsonify({"error": "Artist URL is required"}), 400

    events = scrape_past_events(artist_url)

    for event in events:
        full_address = f"{event['address']}, {event['city']}, {event['state']} {event['zip']}"
        lat_lon = get_lat_lon(full_address)
        if lat_lon:
            event["lat"], event["lon"] = lat_lon

    geojson_data = create_geojson(events)

    return jsonify({"status": "completed", "geojson": geojson_data})

@app.route("/download", methods=["GET"])
def download_geojson():
    """Allows users to download the generated GeoJSON file."""
    if os.path.exists(GEOJSON_STORAGE):
        return send_file(GEOJSON_STORAGE, as_attachment=True, mimetype="application/json")
    return jsonify({"type": "FeatureCollection", "features": []})

if __name__ == "__main__":
    app.run(debug=True)
