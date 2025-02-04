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

# ✅ Set Google Chrome & Chromedriver paths from Heroku environment
CHROMEDRIVER_PATH = os.getenv("CHROMEDRIVER_PATH", "/app/.chromedriver/bin/chromedriver")
GOOGLE_CHROME_BIN = os.getenv("GOOGLE_CHROME_BIN", "/app/.chrome-for-testing/chrome-linux64/chrome")

chrome_options = Options()
chrome_options.binary_location = GOOGLE_CHROME_BIN
chrome_options.add_argument("--headless")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--no-sandbox")

service = Service(CHROMEDRIVER_PATH)

# ✅ Function to extract latitude & longitude from event URL
def get_event_location(url):
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.get(url)
    sleep(3)  # Let page load

    # Example: Modify XPath based on actual website structure
    try:
        venue_address = driver.find_element("xpath", "//div[@class='venue-address']").text
    except Exception as e:
        print("Could not find address:", e)
        driver.quit()
        return None, None, None

    driver.quit()

    # Convert address to latitude & longitude using Google Maps API
    GMAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
    geocode_url = f"https://maps.googleapis.com/maps/api/geocode/json?address={venue_address}&key={GMAPS_API_KEY}"
    response = requests.get(geocode_url).json()

    if response["status"] == "OK":
        location = response["results"][0]["geometry"]["location"]
        lat, lon = location["lat"], location["lng"]
        return lat, lon, venue_address
    else:
        return None, None, None

# ✅ Function to create a bounding polygon for venue
def create_venue_polygon(lat, lon):
    buffer_distance = 0.001  # Adjust for size (~100m)
    venue_polygon = Polygon([
        (lon - buffer_distance, lat - buffer_distance),
        (lon - buffer_distance, lat + buffer_distance),
        (lon + buffer_distance, lat + buffer_distance),
        (lon + buffer_distance, lat - buffer_distance),
        (lon - buffer_distance, lat - buffer_distance)
    ])
    return venue_polygon

# ✅ API Endpoint to handle uploaded URLs
@app.route('/process-urls', methods=['POST'])
def process_urls():
    data = request.get_json()
    urls = data.get("urls", [])
    geojson_features = []

    for url in urls:
        lat, lon, venue_address = get_event_location(url)

        if lat and lon:
            venue_polygon = create_venue_polygon(lat, lon)
            feature = geojson.Feature(
                geometry=venue_polygon,
                properties={
                    "venue_address": venue_address,
                    "latitude": lat,
                    "longitude": lon
                }
            )
            geojson_features.append(feature)

    geojson_data = geojson.FeatureCollection(geojson_features)
    
    with open("venue_data.geojson", "w") as f:
        json.dump(geojson_data, f)

    return jsonify({"message": "GeoJSON file created", "file": "/download-geojson"}), 200

# ✅ Download GeoJSON file
@app.route('/download-geojson')
def download_geojson():
    return send_file("venue_data.geojson", as_attachment=True)

# ✅ Render HTML Upload Page
@app.route('/')
def index():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)
