import os
import time
import json
import yagmail
import simplekml
import googlemaps
from flask import Flask, render_template, request, send_file
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

app = Flask(__name__)

# Load Google Maps API Key from environment variables
GMAPS_API_KEY = os.getenv("GMAPS_API_KEY")
gmaps = googlemaps.Client(key=GMAPS_API_KEY)

# Configure ChromeDriver (Headless)
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

# Global WebDriver session (Optimized)
driver = webdriver.Chrome(options=chrome_options)


@app.route("/")
def index():
    """Render the home page."""
    return render_template("index.html")


@app.route("/start_scraping", methods=["POST"])
def start_scraping():
    """Scrape event data from uploaded URLs and generate KML/GeoJSON."""
    try:
        # Load URLs from JSON request
        data = request.get_json()
        urls = data.get("urls", [])

        if not urls:
            return json.dumps({"status": "error", "message": "No URLs provided."}), 400

        events = []

        for url in urls:
            driver.get(url)
            time.sleep(2)  # Let the page load

            try:
                # Extract event details
                event_name = driver.find_element(By.CSS_SELECTOR, "h2.EfW1v6YNlQnbyB7fUHmR").text
                venue_name = driver.find_element(By.CSS_SELECTOR, "a.q1Vlsw1cdclAUZ4gBvAn").text
                city_state = driver.find_element(By.CSS_SELECTOR, "a[href*='/c/']").text
                address = driver.find_element(By.CSS_SELECTOR, "div").text

                # Extract ZIP code from city_state string
                parts = city_state.split()
                zip_code = parts[-1] if parts[-1].isdigit() else ""

                # Geocode Address with Google Maps API
                full_address = f"{address}, {city_state}"
                geocode_result = gmaps.geocode(full_address)

                if geocode_result:
                    lat = geocode_result[0]["geometry"]["location"]["lat"]
                    lng = geocode_result[0]["geometry"]["location"]["lng"]
                else:
                    lat, lng = 0, 0  # Default (if geocode fails)

                event_data = {
                    "event_name": event_name,
                    "venue": venue_name,
                    "address": address,
                    "city_state": city_state,
                    "zip": zip_code,
                    "lat": lat,
                    "lng": lng,
                }

                events.append(event_data)

            except Exception as e:
                print(f"Error scraping {url}: {e}")

        if not events:
            return json.dumps({"status": "error", "message": "No valid event data found."}), 400

        # Generate KML and GeoJSON files
        kml = simplekml.Kml()
        geojson_data = {"type": "FeatureCollection", "features": []}

        for event in events:
            kml.newpoint(name=event["event_name"], description=event["venue"], coords=[(event["lng"], event["lat"])])

            geojson_data["features"].append({
                "type": "Feature",
                "properties": {
                    "event_name": event["event_name"],
                    "venue": event["venue"],
                    "address": event["address"],
                    "city_state": event["city_state"],
                    "zip": event["zip"],
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [event["lng"], event["lat"]],
                },
            })

