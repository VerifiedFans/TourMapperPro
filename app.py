import json
import os
import logging
from flask import Flask, request, jsonify, render_template, send_from_directory
from googlemaps import Client as GoogleMaps

# Initialize Flask app
app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.INFO)

# Google Maps API Key (Ensure you set this in your environment variables)
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
gmaps = GoogleMaps(key=GOOGLE_MAPS_API_KEY)

# Storage for URLs (temporary in-memory storage)
uploaded_urls = []

# Path to static folder for GeoJSON/KML files
STATIC_FOLDER = os.path.join(app.root_path, "static")
if not os.path.exists(STATIC_FOLDER):
    os.makedirs(STATIC_FOLDER)


@app.route("/")
def index():
    """Render the main page."""
    return render_template("index.html")


@app.route("/upload_urls", methods=["POST"])
def upload_urls():
    """Store uploaded URLs from the frontend."""
    global uploaded_urls
    uploaded_urls = request.json.get("urls", [])
    
    logging.info(f"Uploaded URLs: {uploaded_urls}")
    
    return jsonify({"message": "URLs uploaded successfully"})


@app.route("/view_urls", methods=["GET"])
def view_urls():
    """Return the uploaded URLs for debugging."""
    return jsonify({"uploaded_urls": uploaded_urls})


@app.route("/start_scraping", methods=["POST"])
def start_scraping():
    """Scrape venue data and save as GeoJSON and KML."""
    if not uploaded_urls:
        logging.warning("No URLs uploaded before scraping.")
        return jsonify({"error": "No URLs uploaded"}), 400

    venues = []
    
    # Scrape venues using Google Places API
    for url in uploaded_urls:
        venue_data = get_venue_data(url)
        if venue_data:
            venues.append(venue_data)
    
    logging.info(f"Scraped {len(venues)} venues.")

    # Save as GeoJSON & KML
    save_geojson(venues)
    save_kml(venues)
    
    return jsonify({"message": "Scraping completed"})


def get_venue_data(place_name):
    """Retrieve venue details using Google Places API."""
    try:
        result = gmaps.geocode(place_name)
        if result:
            location = result[0]["geometry"]["location"]
            venue = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [location["lng"], location["lat"]],
                },
                "properties": {
                    "name": result[0]["formatted_address"],
                },
            }
            logging.info(f"Retrieved venue: {venue}")
            return venue
        else:
            logging.warning(f"No results found for: {place_name}")
            return None
    except Exception as e:
        logging.error(f"Error fetching data for {place_name}: {str(e)}")
        return None


def save_geojson(venues):
    """Save venue data as a GeoJSON file."""
    geojson_data = {"type": "FeatureCollection", "features": venues}

    geojson_path = os.path.join(STATIC_FOLDER, "events.geojson")
    
    with open(geojson_path, "w") as f:
        json.dump(geojson_data, f, indent=4)

    file_size = os.path.getsize(geojson_path)
    logging.info(f"Saved GeoJSON ({file_size} bytes) at {geojson_path}")


def save_kml(venues):
    """Save venue data as a KML file."""
    kml_path = os.path.join(STATIC_FOLDER, "events.kml")
    
    kml_template = """<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
    <Document>
    {placemarks}
    </Document>
    </kml>"""
    
    placemarks = ""
    for venue in venues:
        lon, lat = venue["geometry"]["coordinates"]
        name = venue["properties"]["name"]
        placemarks += f"""
        <Placemark>
            <name>{name}</name>
            <Point><coordinates>{lon},{lat},0</coordinates></Point>
        </Placemark>"""
    
    kml_data = kml_template.format(placemarks=placemarks)
    
    with open(kml_path, "w") as f:
        f.write(kml_data)

    file_size = os.path.getsize(kml_path)
    logging.info(f"Saved KML ({file_size} bytes) at {kml_path}")


@app.route("/static/<filename>")
def serve_static(filename):
    """Serve static files (GeoJSON/KML)."""
    return send_from_directory(STATIC_FOLDER, filename)


if __name__ == "__main__":
    app.run(debug=True)
