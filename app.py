import os
import json
import time
from flask import Flask, render_template, request, jsonify, send_file
from celery import Celery
import redis
import requests
from bs4 import BeautifulSoup
from shapely.geometry import Polygon, mapping
import geojson

# Flask app
app = Flask(__name__)

# Redis & Celery Config
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

celery = Celery(
    app.name,
    broker=redis_url,
    backend=redis_url
)

# Ensure Redis is available
try:
    redis_client = redis.from_url(redis_url)
    redis_client.ping()
    print("✅ Redis Connected!")
except redis.exceptions.ConnectionError as e:
    print(f"🔴 Redis Connection Failed: {e}")

# Scraping Function (Extract Venue Info)
def scrape_venue_data(url):
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')

        # Extracting venue details (modify selectors as needed)
        venue_name = soup.find("h1").text.strip()
        address = soup.find("p", class_="address").text.strip()
        city_state_zip = soup.find("p", class_="city-state-zip").text.strip()

        # Fake Lat/Lon for Demo (replace with actual geocoding logic)
        lat, lon = 37.7749, -122.4194

        return {
            "venue_name": venue_name,
            "address": address,
            "city_state_zip": city_state_zip,
            "latitude": lat,
            "longitude": lon
        }
    except Exception as e:
        return {"error": f"Failed to scrape {url}: {str(e)}"}

# Celery Task
@celery.task(bind=True)
def process_urls(self, urls):
    geojson_features = []
    
    for index, url in enumerate(urls):
        venue_data = scrape_venue_data(url)

        if "error" in venue_data:
            continue  # Skip if scraping failed

        polygon = Polygon([
            (venue_data["longitude"] - 0.001, venue_data["latitude"] - 0.001),
            (venue_data["longitude"] + 0.001, venue_data["latitude"] - 0.001),
            (venue_data["longitude"] + 0.001, venue_data["latitude"] + 0.001),
            (venue_data["longitude"] - 0.001, venue_data["latitude"] + 0.001),
            (venue_data["longitude"] - 0.001, venue_data["latitude"] - 0.001),
        ])

        feature = geojson.Feature(
            geometry=mapping(polygon),
            properties={
                "venue_name": venue_data["venue_name"],
                "address": venue_data["address"],
                "city_state_zip": venue_data["city_state_zip"],
                "date": "2025-02-04"
            }
        )
        geojson_features.append(feature)

        # Update progress
        self.update_state(state='PROGRESS', meta={'current': index + 1, 'total': len(urls)})

    # Save as GeoJSON
    geojson_data = geojson.FeatureCollection(geojson_features)
    output_file = "output.geojson"
    with open(output_file, "w") as f:
        json.dump(geojson_data, f)

    return {"status": "completed", "file_path": output_file}

# Route: Home Page
@app.route("/")
def index():
    return render_template("index.html")

# Route: Handle File Upload
@app.route("/upload", methods=["POST"])
def upload():
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files['file']
    urls = file.read().decode("utf-8").splitlines()

    task = process_urls.apply_async(args=[urls])
    return jsonify({"task_id": task.id})

# Route: Get Task Status
@app.route("/task-status/<task_id>")
def task_status(task_id):
    task = process_urls.AsyncResult(task_id)
    if task.state == "PENDING":
        response = {"state": task.state, "progress": 0}
    elif task.state == "PROGRESS":
        response = {"state": task.state, "progress": (task.info["current"] / task.info["total"]) * 100}
    elif task.state == "SUCCESS":
        response = {"state": task.state, "progress": 100, "file_url": "/download"}
    else:
        response = {"state": task.state}
    
    return jsonify(response)

# Route: Download Processed File
@app.route("/download")
def download():
    return send_file("output.geojson", as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)
