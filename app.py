from flask import Flask, render_template, request, jsonify, send_file
import os
import json
import time
import requests

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

uploaded_urls = []
scraping_progress = 0

GOOGLE_MAPS_API_KEY = "YOUR_GOOGLE_MAPS_API_KEY"

def get_coordinates(venue_name):
    """Fetch real coordinates using Google Maps API."""
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={venue_name}&key={GOOGLE_MAPS_API_KEY}"
    response = requests.get(url)
    data = response.json()
    
    if data["status"] == "OK":
        location = data["results"][0]["geometry"]["location"]
        return location["lat"], location["lng"]
    return None, None

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload():
    global uploaded_urls
    if "file" in request.files:
        file = request.files["file"]
        if file.filename.endswith(".txt") or file.filename.endswith(".csv"):
            file_path = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(file_path)
            with open(file_path, "r") as f:
                uploaded_urls = [line.strip() for line in f.readlines()]
    elif "pasted_urls" in request.form:
        pasted_urls = request.form["pasted_urls"].strip().split("\n")
        uploaded_urls = [url.strip() for url in pasted_urls if url.strip()]
    return jsonify({"uploaded_urls": uploaded_urls})

@app.route("/view_files")
def view_files():
    return jsonify({"uploaded_urls": uploaded_urls})

@app.route("/clear_files", methods=["POST"])
def clear_files():
    global uploaded_urls
    uploaded_urls = []
    return jsonify({"message": "Uploaded files cleared."})

@app.route("/start_scraping", methods=["POST"])
def start_scraping():
    global scraping_progress
    scraping_progress = 0

    if not uploaded_urls:
        return jsonify({"error": "No URLs uploaded."}), 400

    geojson_data = {
        "type": "FeatureCollection",
        "features": []
    }

    for i, url in enumerate(uploaded_urls):
        time.sleep(1)  

        venue_name = f"Venue {i+1}"  # This should be replaced with actual scraped venue names
        latitude, longitude = get_coordinates(venue_name)

        if latitude is None or longitude is None:
            latitude, longitude = 37.7749, -122.4194  # Default to San Francisco

        address = f"Real address for {venue_name}"  # Replace with actual scraped address

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [longitude, latitude]
            },
            "properties": {
                "url": url,
                "venue_name": venue_name,
                "address": address
            }
        }
        geojson_data["features"].append(feature)

        scraping_progress = int(((i + 1) / len(uploaded_urls)) * 100)

    geojson_path = os.path.join(UPLOAD_FOLDER, "scraped_data.geojson")
    with open(geojson_path, "w") as f:
        json.dump(geojson_data, f, indent=4)

    return jsonify({"message": "Scraping completed.", "progress": scraping_progress})

@app.route("/progress")
def progress():
    return jsonify({"progress": scraping_progress})

@app.route("/download")
def download_geojson():
    geojson_path = os.path.join(UPLOAD_FOLDER, "scraped_data.geojson")
    if os.path.exists(geojson_path):
        return send_file(geojson_path, as_attachment=True)
    return jsonify({"error": "No scraped data found."}), 404

if __name__ == "__main__":
    app.run(debug=True)
