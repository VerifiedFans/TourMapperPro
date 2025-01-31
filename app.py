from flask import Flask, request, jsonify, render_template, send_from_directory
import logging
import os
import json
import time
import simplekml
import googlemaps
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import geopy.distance

# Initialize Flask app
app = Flask(__name__, template_folder="templates")

# Enable logging for debugging
logging.basicConfig(level=logging.DEBUG)

# Store URLs in memory
stored_urls = []

# Set up Google Maps API
GOOGLE_MAPS_API_KEY = "YOUR_GOOGLE_MAPS_API_KEY"  # Replace with your API Key
gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

@app.route('/')
def home():
    """Serve the main HTML page."""
    return render_template("index.html")

@app.route('/upload_urls', methods=['POST'])
def upload_urls():
    """Receive and store URLs."""
    try:
        data = request.get_json()
        if not data or 'urls' not in data:
            return jsonify({"message": "Invalid request. No URLs received."}), 400

        urls = data['urls']
        if not isinstance(urls, list) or not all(isinstance(url, str) for url in urls):
            return jsonify({"message": "Invalid data format. Expecting a list of URLs."}), 400

        stored_urls.extend(urls)
        logging.info(f"Stored URLs: {stored_urls}")
        return jsonify({"message": "URLs uploaded successfully!"}), 200

    except Exception as e:
        logging.error(f"Upload URLs error: {str(e)}")
        return jsonify({"message": f"Error: {str(e)}"}), 500

@app.route('/view_urls', methods=['GET'])
def view_urls():
    """Retrieve stored URLs."""
    return jsonify({"urls": stored_urls})

@app.route('/clear_urls', methods=['POST'])
def clear_urls():
    """Clear stored URLs."""
    global stored_urls
    stored_urls = []
    return jsonify({"message": "Stored URLs cleared successfully."})

def extract_coordinates(soup):
    """Extract venue latitude & longitude from the page."""
    try:
        lat_tag = soup.find("meta", {"property": "place:location:latitude"})
        lon_tag = soup.find("meta", {"property": "place:location:longitude"})

        if lat_tag and lon_tag:
            return float(lat_tag["content"]), float(lon_tag["content"])

    except Exception as e:
        logging.error(f"Error extracting coordinates: {str(e)}")

    return None, None  # Default if not found

def generate_polygon(lat, lon, size=0.002):
    """Generate a square polygon around the venue (size ≈ 200m)."""
    return [
        (lat + size, lon - size),
        (lat + size, lon + size),
        (lat - size, lon + size),
        (lat - size, lon - size),
        (lat + size, lon - size)
    ]

def find_parking_areas(venue_lat, venue_lon):
    """Find parking areas near the venue, avoiding main roads."""
    try:
        places = gmaps.places_nearby(
            location=(venue_lat, venue_lon),
            radius=500,
            type="parking"
        )

        parking_polygons = []
        for place in places.get("results", []):
            lat = place["geometry"]["location"]["lat"]
            lon = place["geometry"]["location"]["lng"]

            parking_polygon = generate_polygon(lat, lon, size=0.0015)

            if not crosses_main_roads(parking_polygon):
                parking_polygons.append(parking_polygon)

        return parking_polygons

    except Exception as e:
        logging.error(f"Error finding parking areas: {str(e)}")
        return []

def crosses_main_roads(polygon):
    """Check if a polygon crosses a main road."""
    try:
        for lat, lon in polygon:
            roads = gmaps.roads.snap_to_roads([(lat, lon)])
            for road in roads.get("snappedPoints", []):
                if "highway" in road["placeId"]:
                    return True
    except Exception as e:
        logging.error(f"Error checking road crossings: {str(e)}")
    return False

@app.route('/start_scraping', methods=['POST'])
def start_scraping():
    """Scrape venue & parking polygon coordinates and generate KML & GeoJSON."""
    try:
        if not stored_urls:
            return jsonify({"message": "No URLs to scrape."}), 400

        results = []

        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        service = Service()
        driver = webdriver.Chrome(service=service, options=chrome_options)

        for url in stored_urls:
            driver.get(url)
            time.sleep(3)

            soup = BeautifulSoup(driver.page_source, "html.parser")
            title = soup.find("title").text if soup.find("title") else "No title found"

            venue_lat, venue_lon = extract_coordinates(soup)

            if venue_lat and venue_lon:
                venue_polygon = generate_polygon(venue_lat, venue_lon)
                parking_polygons = find_parking_areas(venue_lat, venue_lon)

                event_info = {
                    "url": url,
                    "title": title,
                    "venue_polygon": venue_polygon,
                    "parking_polygons": parking_polygons
                }
                results.append(event_info)

        driver.quit()

        generate_kml(results)
        generate_geojson(results)

        return jsonify({"message": "Scraping completed!", "data": results})

    except Exception as e:
        logging.error(f"Scraping error: {str(e)}")
        return jsonify({"message": f"Error: {str(e)}"}), 500

def generate_kml(events):
    """Generate a KML file with venue & parking polygons."""
    os.makedirs("static", exist_ok=True)
    kml = simplekml.Kml()

    for event in events:
        venue_polygon = kml.newpolygon(name=event["title"])
        venue_polygon.outerboundaryis = event["venue_polygon"]

        for parking in event["parking_polygons"]:
            parking_polygon = kml.newpolygon(name="Parking Area")
            parking_polygon.outerboundaryis = parking

    kml.save("static/events.kml")

def generate_geojson(events):
    """Generate a GeoJSON file with venue & parking polygons."""
    os.makedirs("static", exist_ok=True)
    geojson_data = {"type": "FeatureCollection", "features": []}

    for event in events:
        geojson_data["features"].append({
            "type": "Feature",
            "properties": {"title": event["title"]},
            "geometry": {"type": "Polygon", "coordinates": [event["venue_polygon"]]}
        })
        for parking in event["parking_polygons"]:
            geojson_data["features"].append({
                "type": "Feature",
                "properties": {"title": "Parking Area"},
                "geometry": {"type": "Polygon", "coordinates": [parking]}
            })

    with open("static/events.geojson", "w") as file:
        json.dump(geojson_data, file, indent=4)

@app.route('/static/<path:filename>')
def static_files(filename):
    """Serve static files from the 'static' directory."""
    return send_from_directory('static', filename)

if __name__ == '__main__':
    app.run(debug=True)
