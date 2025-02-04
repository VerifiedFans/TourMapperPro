import os
import json
import requests
from flask import Flask, request, render_template, send_file
from bs4 import BeautifulSoup
from shapely.geometry import Point, Polygon, mapping
import simplekml
import geopy
from geopy.geocoders import Nominatim

# Flask App Initialization
app = Flask(__name__)

# Geocoder Initialization
geolocator = Nominatim(user_agent="tourmapper")

# Function to Scrape Event URL for Address
def scrape_event_page(url):
    """Extracts venue address from event webpage"""
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print(f"Failed to fetch: {url}")
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    
    # Modify selectors based on actual event website structure
    address = soup.find("span", {"class": "venue-address"}) or \
              soup.find("div", {"class": "event-location"}) or \
              soup.find("p", {"class": "address"})

    if address:
        return address.text.strip()
    
    return "Address Not Found"

# Convert Address to Lat/Lon
def get_lat_lon(address):
    """Converts an address to latitude and longitude"""
    try:
        location = geolocator.geocode(address)
        if location:
            return location.latitude, location.longitude
    except:
        return None
    return None

# Create Polygon Around Venue & Parking Areas
def create_polygon(lat, lon):
    """Generates a simple polygon around the venue and parking"""
    offset = 0.001  # Adjust for larger/smaller polygons
    return Polygon([
        (lon - offset, lat - offset),
        (lon + offset, lat - offset),
        (lon + offset, lat + offset),
        (lon - offset, lat + offset),
        (lon - offset, lat - offset)  # Close the polygon
    ])

# Save to GeoJSON File
def save_geojson(geojson_data, filename="static/events.geojson"):
    """Saves data as a GeoJSON file"""
    if not geojson_data.get("features"):
        print("No valid event data found. Skipping file generation.")
        return
    
    with open(filename, "w", encoding="utf-8") as geojson_file:
        json.dump(geojson_data, geojson_file, indent=2)
    
    print(f"GeoJSON file saved: {filename}")

# Route for Main Page
@app.route('/')
def index():
    return render_template('index.html')

# Route for Uploading & Processing URLs
@app.route('/process-urls', methods=['POST'])
def process_urls():
    uploaded_urls = request.form.get("urls")
    if not uploaded_urls:
        return "No URLs provided."

    urls = uploaded_urls.split("\n")
    
    features = []

    for url in urls:
        url = url.strip()
        if not url:
            continue

        address = scrape_event_page(url)
        if address == "Address Not Found":
            continue

        latlon = get_lat_lon(address)
        if not latlon:
            continue

        lat, lon = latlon
        polygon = create_polygon(lat, lon)

        # Prepare GeoJSON Feature
        feature = {
            "type": "Feature",
            "geometry": mapping(polygon),
            "properties": {
                "venue": address,
                "lat": lat,
                "lon": lon,
                "source_url": url
            }
        }
        features.append(feature)

    geojson_data = {"type": "FeatureCollection", "features": features}
    save_geojson(geojson_data)

    return "GeoJSON file generated successfully."

# Route for Downloading GeoJSON File
@app.route('/download-geojson')
def download_geojson():
    return send_file("static/events.geojson", as_attachment=True)

# Run Flask App
if __name__ == '__main__':
    app.run(debug=True)
