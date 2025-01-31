import os
import json
from flask import Flask, request, jsonify, render_template, send_from_directory
import googlemaps
import geopy.distance
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# Initialize Flask app
app = Flask(__name__)

# Ensure 'static' directory exists for file storage
STATIC_FOLDER = "static"
if not os.path.exists(STATIC_FOLDER):
    os.makedirs(STATIC_FOLDER)

# Get Google Maps API Key from environment variable
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
if not GOOGLE_MAPS_API_KEY:
    raise ValueError("⚠️ Missing Google Maps API Key! Set GOOGLE_MAPS_API_KEY in Heroku.")

# Initialize Google Maps Client
gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

# Store uploaded URLs globally
stored_urls = []

# --- Route: Home ---
@app.route('/')
def home():
    return render_template('index.html')

# --- Route: Upload URLs ---
@app.route('/upload_urls', methods=['POST'])
def upload_urls():
    data = request.get_json()
    if 'urls' not in data:
        return jsonify({"error": "No URLs provided"}), 400
    
    urls = data['urls']
    stored_urls.extend(urls)

    return jsonify({"message": "URLs uploaded successfully", "stored_urls": stored_urls})

# --- Route: Start Scraping ---
@app.route('/start_scraping', methods=['POST'])
def start_scraping():
    if not stored_urls:
        return jsonify({"error": "No URLs available for scraping"}), 400
    
    venue_data = []
    
    # Configure Selenium WebDriver
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")

    driver = webdriver.Chrome(options=chrome_options)

    for url in stored_urls:
        driver.get(url)
        soup = BeautifulSoup(driver.page_source, 'html.parser')

        # Extract latitude and longitude from the webpage
        lat, lon = extract_lat_lon(soup)
        venue_data.append({"url": url, "latitude": lat, "longitude": lon})

    driver.quit()

    # Generate KML and GeoJSON files
    kml_filename = save_kml(venue_data)
    geojson_filename = save_geojson(venue_data)

    return jsonify({
        "message": "Scraping completed!",
        "kml_file": f"/download/{kml_filename}",
        "geojson_file": f"/download/{geojson_filename}"
    })

# --- Extract Latitude & Longitude from Webpage ---
def extract_lat_lon(soup):
    lat, lon = None, None
    # Example: Extract lat/lon from meta tags
    lat_meta = soup.find("meta", {"property": "place:location:latitude"})
    lon_meta = soup.find("meta", {"property": "place:location:longitude"})

    if lat_meta and lon_meta:
        lat = float(lat_meta["content"])
        lon = float(lon_meta["content"])

    return lat, lon

# --- Generate KML File ---
def save_kml(venue_data):
    kml_content = '<?xml version="1.0" encoding="UTF-8"?>\n'
    kml_content += '<kml xmlns="http://www.opengis.net/kml/2.2">\n'
    kml_content += "<Document>\n"

    for venue in venue_data:
        kml_content += f"""
        <Placemark>
            <name>{venue['url']}</name>
            <Point>
                <coordinates>{venue['longitude']},{venue['latitude']},0</coordinates>
            </Point>
        </Placemark>
        """

    kml_content += "</Document>\n</kml>"

    filename = "venues.kml"
    filepath = os.path.join(STATIC_FOLDER, filename)
    with open(filepath, "w") as file:
        file.write(kml_content)

    return filename

# --- Generate GeoJSON File ---
def save_geojson(venue_data):
    geojson = {
        "type": "FeatureCollection",
        "features": []
    }

    for venue in venue_data:
        geojson["features"].append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [venue["longitude"], venue["latitude"]]
            },
            "properties": {
                "url": venue["url"]
            }
        })

    filename = "venues.geojson"
    filepath = os.path.join(STATIC_FOLDER, filename)
    with open(filepath, "w") as file:
        json.dump(geojson, file)

    return filename

# --- Route: Download Files ---
@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(STATIC_FOLDER, filename, as_attachment=True)

# --- Start Flask App ---
if __name__ == '__main__':
    app.run(debug=True)
