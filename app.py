import os
import json
import geojson
import requests
from flask import Flask, render_template, request, jsonify, send_file
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from shapely.geometry import Point, Polygon
from time import sleep

app = Flask(__name__)

# ✅ Heroku Environment Variables
CHROMEDRIVER_PATH = os.getenv("CHROMEDRIVER_PATH", "/app/.chromedriver/bin/chromedriver")
GOOGLE_CHROME_BIN = os.getenv("GOOGLE_CHROME_BIN", "/app/.chrome-for-testing/chrome-linux64/chrome")
GMAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

chrome_options = Options()
chrome_options.binary_location = GOOGLE_CHROME_BIN
chrome_options.add_argument("--headless")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--no-sandbox")

service = Service(CHROMEDRIVER_PATH)

# ✅ Function to Extract Event Details from URL
def scrape_event_details(url):
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.get(url)
    sleep(5)  # Let JavaScript elements load

    venue_name, venue_address, event_date = None, None, None

    try:
        # 🛠 Modify based on actual website HTML structure
        venue_name = driver.find_element("xpath", "//h1[@class='venue-name']").text.strip()
        venue_address = driver.find_element("xpath", "//div[@class='venue-address']").text.strip()
        event_date = driver.find_element("xpath", "//div[@class='event-date']").text.strip()

        print(f"✅ Scraped Data: {venue_name}, {venue_address}, {event_date}")

    except Exception as e:
        print(f"❌ Error scraping {url}: {e}")

    driver.quit()
    return venue_name, venue_address, event_date

# ✅ Function to Get Lat/Lon from Google Maps API
def get_coordinates(address):
    lat, lon = None, None
    geocode_url = f"https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={GMAPS_API_KEY}"

    try:
        response = requests.get(geocode_url).json()
        if response["status"] == "OK":
            location = response["results"][0]["geometry"]["location"]
            lat, lon = location["lat"], location["lng"]
            print(f"✅ Geocoded: {lat}, {lon}")
    except Exception as e:
        print(f"❌ Google Maps API Error: {e}")

    return lat, lon

# ✅ Function to Draw Polygon for Venue & Parking
def create_venue_polygon(lat, lon):
    buffer_distance = 0.001  # Adjust for size (~100m)
    return Polygon([
        (lon - buffer_distance, lat - buffer_distance),
        (lon - buffer_distance, lat + buffer_distance),
        (lon + buffer_distance, lat + buffer_distance),
        (lon + buffer_distance, lat - buffer_distance),
        (lon - buffer_distance, lat - buffer_distance)
    ])

# ✅ API Endpoint for Uploading Event URLs
@app.route('/process-urls', methods=['POST'])
def process_urls():
    data = request.get_json()
    urls = data.get("urls", [])
    geojson_features = []

    for url in urls:
        venue_name, venue_address, event_date = scrape_event_details(url)
        if venue_address:
            lat, lon = get_coordinates(venue_address)
            if lat and lon:
                venue_polygon = create_venue_polygon(lat, lon)
                feature = geojson.Feature(
                    geometry=venue_polygon,
                    properties={
                        "venue_name": venue_name,
                        "venue_address": venue_address,
                        "latitude": lat,
                        "longitude": lon,
                        "event_date": event_date
                    }
                )
                geojson_features.append(feature)

    if not geojson_features:
        return jsonify({"error": "No valid locations found"}), 400

    geojson_data = geojson.FeatureCollection(geojson_features)
    with open("event_venues.geojson", "w") as f:
        json.dump(geojson_data, f)

    return jsonify({"message": "GeoJSON file created", "file": "/download-geojson"}), 200

# ✅ API Endpoint to Download GeoJSON
@app.route('/download-geojson')
def download_geojson():
    return send_file("event_venues.geojson", as_attachment=True)

# ✅ Load HTML Upload Page
@app.route('/')
def index():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)
