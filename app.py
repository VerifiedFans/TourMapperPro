import os
import json
import time
import yagmail
import requests
from flask import Flask, request, jsonify, render_template
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from bs4 import BeautifulSoup
from webdriver_manager.chrome import ChromeDriverManager

# ✅ Load API Keys
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
EMAIL_USER = os.getenv("EMAIL_USER")  # Your email
EMAIL_PASS = os.getenv("EMAIL_PASS")  # Your email app password

# ✅ Initialize Flask App
app = Flask(__name__)

# ✅ Selenium Setup
chrome_options = webdriver.ChromeOptions()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()),
    options=chrome_options
)

# ✅ Function: Scrape Event Data
def scrape_event_data(url):
    """Scrapes event date, venue name, and address from a URL."""
    driver.get(url)
    time.sleep(2)
    soup = BeautifulSoup(driver.page_source, "html.parser")

    event_date = soup.find("span", class_="event-date").text.strip() if soup.find("span", class_="event-date") else "Unknown Date"
    venue_name = soup.find("h2", class_="venue-name").text.strip() if soup.find("h2", class_="venue-name") else "Unknown Venue"
    address = soup.find("p", class_="venue-address").text.strip() if soup.find("p", class_="venue-address") else "Unknown Address"

    return {"date": event_date, "venue": venue_name, "address": address}

# ✅ Function: Get Lat/Lon from Google Maps API
def get_lat_lng(address):
    """Fetches latitude & longitude for a given address."""
    params = {"address": address, "key": GOOGLE_MAPS_API_KEY}
    response = requests.get("https://maps.googleapis.com/maps/api/geocode/json", params=params)
    data = response.json()

    if data["status"] == "OK":
        location = data["results"][0]["geometry"]["location"]
        return location["lat"], location["lng"]
    return None, None

# ✅ Function: Fetch Venue & Parking Polygons from OpenStreetMap Overpass API
def get_osm_polygons(lat, lon):
    """Fetches venue & parking lot polygons from OpenStreetMap Overpass API."""
    overpass_url = "http://overpass-api.de/api/interpreter"
    query = f"""
    [out:json];
    (
      way(around:50,{lat},{lon})["building"];
      way(around:100,{lat},{lon})["amenity"="parking"];
    );
    out geom;
    """
    response = requests.get(overpass_url, params={"data": query})
    data = response.json()

    polygons = {"venue": None, "parking_lots": []}

    if "elements" in data:
        for element in data["elements"]:
            if "geometry" in element:
                coords = [(point["lon"], point["lat"]) for point in element["geometry"]]
                if "building" in element["tags"]:
                    polygons["venue"] = coords
                elif "amenity" in element["tags"] and element["tags"]["amenity"] == "parking":
                    polygons["parking_lots"].append(coords)

    return polygons

# ✅ Function: Generate Single GeoJSON
def generate_geojson(events):
    """Creates a single GeoJSON file for venues & parking lots."""
    geojson_data = {"type": "FeatureCollection", "features": []}

    for event in events:
        lat, lon = get_lat_lng(event["address"])
        if lat and lon:
            polygons = get_osm_polygons(lat, lon)

            if polygons["venue"]:
                geojson_data["features"].append({
                    "type": "Feature",
                    "geometry": {"type": "Polygon", "coordinates": [polygons["venue"]]},
                    "properties": {"name": event["venue"], "date": event["date"], "address": event["address"], "type": "venue"}
                })

            for parking in polygons["parking_lots"]:
                geojson_data["features"].append({
                    "type": "Feature",
                    "geometry": {"type": "Polygon", "coordinates": [parking]},
                    "properties": {"name": f"{event['venue']} Parking", "type": "parking"}
                })

    geojson_path = "static/events.geojson"
    with open(geojson_path, "w") as f:
        json.dump(geojson_data, f, indent=4)

    return geojson_path

# ✅ Function: Send Email
def send_email(file_path):
    """Emails the GeoJSON file to Troy."""
    yag = yagmail.SMTP(EMAIL_USER, EMAIL_PASS)
    yag.send(to="troy@knoxconcepts.com", subject="TourMapper Pro - Venue & Parking Data",
             contents="Attached is the generated GeoJSON file.", attachments=file_path)

# ✅ API Routes
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/start_scraping", methods=["POST"])
def start_scraping():
    urls = request.json.get("urls", [])
    if not urls:
        return jsonify({"error": "No URLs provided"}), 400

    events = [scrape_event_data(url) for url in urls]
    geojson_file = generate_geojson(events)
    send_email(geojson_file)

    return jsonify({"message": "Scraping completed. GeoJSON sent via email."})

# ✅ Run Flask App
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

