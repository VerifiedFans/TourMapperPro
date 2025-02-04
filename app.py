import os
import json
import geojson
import requests
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from celery import Celery
from shapely.geometry import Point, Polygon

app = Flask(__name__)
CORS(app)  # Allow cross-origin requests

# Celery Configuration for Redis (Heroku uses `REDIS_URL`)
app.config["CELERY_BROKER_URL"] = os.getenv("REDIS_URL", "redis://localhost:6379")
app.config["CELERY_RESULT_BACKEND"] = os.getenv("REDIS_URL", "redis://localhost:6379")

def make_celery(app):
    celery = Celery(app.import_name, backend=app.config["CELERY_RESULT_BACKEND"], broker=app.config["CELERY_BROKER_URL"])
    celery.conf.update(app.config)
    return celery

celery = make_celery(app)

# Google Maps API Key
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
if not GOOGLE_MAPS_API_KEY:
    raise ValueError("Missing Google Maps API key. Set it in Heroku.")

# Function to get latitude & longitude from an address using Google Maps API
def get_coordinates(address):
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={GOOGLE_MAPS_API_KEY}"
    response = requests.get(url).json()
    if response["status"] == "OK":
        location = response["results"][0]["geometry"]["location"]
        return location["lat"], location["lng"]
    return None, None

# Function to scrape event details from a given URL
def scrape_event_details(url):
    # This function should be updated based on the website structure being scraped
    # Dummy implementation returning placeholders
    return "Sample Venue", "123 Main St, New York, NY", "2025-12-01"

# Function to create a polygon (dummy example)
def create_venue_polygon(lat, lon):
    size = 0.001  # Approx. 100m square
    return Polygon([
        (lon - size, lat - size),
        (lon + size, lat - size),
        (lon + size, lat + size),
        (lon - size, lat + size),
        (lon - size, lat - size)
    ])

# Celery Task for Processing URLs
@celery.task
def process_urls_task(urls):
    results = []
    for url in urls:
        venue_name, venue_address, event_date = scrape_event_details(url)
        if venue_address:
            lat, lon = get_coordinates(venue_address)
            if lat and lon:
                venue_polygon = create_venue_polygon(lat, lon)
                results.append(
                    geojson.Feature(
                        geometry=venue_polygon,
                        properties={
                            "venue_name": venue_name,
                            "venue_address": venue_address,
                            "latitude": lat,
                            "longitude": lon,
                            "event_date": event_date
                        }
                    )
                )

    geojson_data = geojson.FeatureCollection(results)

    # Save GeoJSON File
    geojson_file = "event_venues.geojson"
    with open(geojson_file, "w") as f:
        json.dump(geojson_data, f)

    return geojson_file  # Return filename

# API Route to Process URLs (Async)
@app.route('/process-urls', methods=['POST'])
def process_urls():
    data = request.get_json()
    urls = data.get("urls", [])

    # Offload processing to Celery
    task = process_urls_task.apply_async(args=[urls])

    return jsonify({"message": "Processing started", "task_id": task.id}), 202

# API Route to Check Task Status
@app.route('/task-status/<task_id>', methods=['GET'])
def task_status(task_id):
    task = process_urls_task.AsyncResult(task_id)
    return jsonify({"status": task.status, "result": task.result})

# API Route to Download GeoJSON
@app.route('/download-geojson', methods=['GET'])
def download_geojson():
    geojson_file = "event_venues.geojson"
    if os.path.exists(geojson_file):
        return send_file(geojson_file, as_attachment=True)
    return jsonify({"error": "GeoJSON file not found"}), 404

if __name__ == "__main__":
    app.run(debug=True)
