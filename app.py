import os
import json
import logging
import requests
from flask import Flask, render_template, request, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

# ✅ Initialize Flask app
app = Flask(__name__)

# ✅ Enable Logging
logging.basicConfig(level=logging.INFO)

# ✅ Load API Key from Heroku Environment Variables
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

# ✅ Set Chrome Options for Selenium
chrome_options = Options()
chrome_options.add_argument("--headless")  # Run in headless mode
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

# ✅ Manually Set Chrome & ChromeDriver Paths
CHROME_PATH = "/app/.chrome-for-testing/chrome-linux64/chrome"
CHROMEDRIVER_PATH = "/app/.chromedriver/bin/chromedriver"

chrome_options.binary_location = CHROME_PATH
service = Service(CHROMEDRIVER_PATH)

# ✅ Initialize WebDriver
try:
    driver = webdriver.Chrome(service=service, options=chrome_options)
    logging.info("Chrome WebDriver started successfully.")
except Exception as e:
    logging.error(f"Error starting Chrome WebDriver: {e}")

# ✅ Route: Serve `index.html`
@app.route("/")
def home():
    return render_template("index.html")

# ✅ Route: Fetch venue & parking data as GeoJSON
@app.route("/get_venue_data", methods=["GET"])
def get_venue_data():
    venue_name = request.args.get("venue")
    if not venue_name:
        return jsonify({"error": "Missing venue parameter"}), 400

    try:
        # 🎯 Step 1: Fetch venue details from Google Maps API
        place_url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
        params = {
            "input": venue_name,
            "inputtype": "textquery",
            "fields": "geometry,place_id,name",
            "key": GOOGLE_MAPS_API_KEY
        }
        place_response = requests.get(place_url, params=params)
        place_data = place_response.json()

        if not place_data.get("candidates"):
            return jsonify({"error": "Venue not found"}), 404

        place = place_data["candidates"][0]
        place_id = place["place_id"]
        location = place["geometry"]["location"]

        # 🎯 Step 2: Fetch venue details
        details_url = "https://maps.googleapis.com/maps/api/place/details/json"
        details_params = {
            "place_id": place_id,
            "fields": "geometry,name,formatted_address",
            "key": GOOGLE_MAPS_API_KEY
        }
        details_response = requests.get(details_url, params=details_params)
        details_data = details_response.json()

        if not details_data.get("result"):
            return jsonify({"error": "Could not fetch venue details"}), 500

        venue_info = details_data["result"]
        address = venue_info.get("formatted_address", "Unknown Address")

        # 🎯 Step 3: Fetch nearby parking locations
        parking_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        parking_params = {
            "location": f"{location['lat']},{location['lng']}",
            "radius": 500,  # 500 meters search radius
            "type": "parking",
            "key": GOOGLE_MAPS_API_KEY
        }
        parking_response = requests.get(parking_url, params=parking_params)
        parking_data = parking_response.json()

        # 🎯 Step 4: Create GeoJSON
        geojson_data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [location["lng"], location["lat"]]
                    },
                    "properties": {
                        "name": venue_info["name"],
                        "address": address,
                        "type": "venue"
                    }
                }
            ]
        }

        # ✅ Add Parking Locations as Polygons
        for parking in parking_data.get("results", []):
            if "geometry" in parking:
                parking_location = parking["geometry"]["location"]
                geojson_data["features"].append({
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[
                            [parking_location["lng"] - 0.0005, parking_location["lat"] - 0.0005],
                            [parking_location["lng"] + 0.0005, parking_location["lat"] - 0.0005],
                            [parking_location["lng"] + 0.0005, parking_location["lat"] + 0.0005],
                            [parking_location["lng"] - 0.0005, parking_location["lat"] + 0.0005],
                            [parking_location["lng"] - 0.0005, parking_location["lat"] - 0.0005]
                        ]]
                    },
                    "properties": {
                        "name": parking["name"],
                        "type": "parking"
                    }
                })

        # 🎯 Step 5: Save GeoJSON to `/static/events.geojson`
        with open("static/events.geojson", "w") as f:
            json.dump(geojson_data, f, indent=4)

        return jsonify(geojson_data)

    except Exception as e:
        logging.error(f"Error fetching venue data: {e}")
        return jsonify({"error": str(e)}), 500

# ✅ Run Flask in production
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)

