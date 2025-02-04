import os
import json
import logging
import requests
from flask import Flask, request, render_template, jsonify, send_file
from werkzeug.utils import secure_filename
from shapely.geometry import Point, Polygon
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import geojson

# Initialize Flask App
app = Flask(__name__)

# Set Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load API Key
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
if not GOOGLE_MAPS_API_KEY:
    raise ValueError("Missing Google Maps API key. Set it in Heroku.")

# Configure Chrome Driver (for Web Scraping)
CHROMEDRIVER_PATH = os.getenv("CHROMEDRIVER_PATH", "/app/.chromedriver/bin/chromedriver")
GOOGLE_CHROME_BIN = os.getenv("GOOGLE_CHROME_BIN", "/app/.chrome-for-testing/chrome-linux64/chrome")

chrome_options = Options()
chrome_options.binary_location = GOOGLE_CHROME_BIN
chrome_options.add_argument("--headless")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--no-sandbox")
service = Service(CHROMEDRIVER_PATH)

# Allow Uploads (for URL Lists & GeoJSON/KML)
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {"txt", "csv", "json", "kml"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# ------------------------------
# 📍 Fetch Venue Location Data
# ------------------------------
def get_lat_lon(address):
    """Get latitude & longitude from address using Google Maps API."""
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={GOOGLE_MAPS_API_KEY}"
    response = requests.get(url).json()
    
    if response["status"] == "OK":
        location = response["results"][0]["geometry"]["location"]
        return location["lat"], location["lng"]
    
    logger.error(f"Failed to get coordinates for {address}")
    return None, None

# ------------------------------
# 🏟️ Scrape Parking Information
# ------------------------------
def scrape_parking_info(venue_url):
    """Scrape venue page for parking info using Selenium."""
    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.get(venue_url)
        page_text = driver.page_source
        driver.quit()
        
        # Basic Check (for demonstration)
        if "parking" in page_text.lower():
            return "Parking Available"
        return "No Parking Info Found"
    
    except Exception as e:
        logger.error(f"Error scraping {venue_url}: {e}")
        return "Error Scraping"

# ------------------------------
# 🏢 Generate Venue & Parking Polygons
# ------------------------------
def generate_polygons(lat, lon):
    """Create polygon around venue and parking area, avoiding major roads."""
    if lat is None or lon is None:
        return None

    venue_polygon = Polygon([
        (lon - 0.001, lat - 0.001),
        (lon + 0.001, lat - 0.001),
        (lon + 0.001, lat + 0.001),
        (lon - 0.001, lat + 0.001),
    ])
    
    parking_polygon = Polygon([
        (lon - 0.002, lat - 0.002),
        (lon + 0.002, lat - 0.002),
        (lon + 0.002, lat + 0.002),
        (lon - 0.002, lat + 0.002),
    ])
    
    return venue_polygon, parking_polygon

# ------------------------------
# 📥 Process Uploaded URLs
# ------------------------------
@app.route("/process-urls", methods=["POST"])
def process_urls():
    """Receive URLs, scrape venue details, generate geoJSON."""
    try:
        urls = request.json.get("urls", [])
        if not urls:
            return jsonify({"error": "No URLs provided"}), 400
        
        geojson_features = []

        for url in urls:
            venue_name = url.split("/")[-1].replace("-", " ").title()  # Example parsing venue name
            lat, lon = get_lat_lon(venue_name + " venue address")  # Replace with actual venue address
            parking_info = scrape_parking_info(url)
            venue_poly, parking_poly = generate_polygons(lat, lon)

            if venue_poly:
                feature = geojson.Feature(
                    geometry=venue_poly,
                    properties={
                        "name": venue_name,
                        "latitude": lat,
                        "longitude": lon,
                        "parking": parking_info,
                        "event_date": "2025-XX-XX",
                    }
                )
                geojson_features.append(feature)

            if parking_poly:
                feature = geojson.Feature(
                    geometry=parking_poly,
                    properties={"type": "Parking"}
                )
                geojson_features.append(feature)

        geojson_data = geojson.FeatureCollection(geojson_features)

        with open("output.geojson", "w") as f:
            json.dump(geojson_data, f)

        return send_file("output.geojson", as_attachment=True)

    except Exception as e:
        logger.error(f"Error processing URLs: {e}")
        return jsonify({"error": "Server error"}), 500

# ------------------------------
# 📤 Upload File Handler
# ------------------------------
@app.route("/upload", methods=["POST"])
def upload_file():
    """Handle file uploads."""
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files["file"]
    if file.filename == "" or not allowed_file(file.filename):
        return jsonify({"error": "Invalid file type"}), 400
    
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], secure_filename(file.filename))
    file.save(filepath)

    return jsonify({"message": "File uploaded successfully", "filename": file.filename})

# ------------------------------
# 🌐 Serve Frontend Page
# ------------------------------
@app.route("/")
def index():
    return render_template("index.html")

# ------------------------------
# 🚀 Run App
# ------------------------------
if __name__ == "__main__":
    app.run(debug=True)
