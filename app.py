import os
import json
import requests
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename

# Flask App Setup
app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Google Maps API Key (Replace with your real key)
API_KEY = "YOUR_GOOGLE_MAPS_API_KEY_HERE"

# Progress tracking
progress = {"value": 0}


def get_coordinates(venue_name):
    """Fetch latitude, longitude, and formatted address using Google Maps API"""
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={venue_name}&key={API_KEY}"
    response = requests.get(url)
    data = response.json()

    if "results" in data and len(data["results"]) > 0:
        location = data["results"][0]["geometry"]["location"]
        formatted_address = data["results"][0]["formatted_address"]
        return location["lat"], location["lng"], formatted_address
    return None, None, "Unknown Address"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload_file():
    """Handles file uploads (TXT, CSV) and manual copy-paste input."""
    uploaded_files = request.files.getlist("file")
    pasted_urls = request.form.get("pasted_urls")

    all_urls = []

    # Process uploaded files
    for file in uploaded_files:
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(file_path)

        with open(file_path, "r") as f:
            all_urls.extend(f.read().splitlines())

    # Process pasted URLs
    if pasted_urls:
        all_urls.extend(pasted_urls.strip().split("\n"))

    # Remove duplicates
    all_urls = list(set(all_urls))

    # Save combined URLs to a file
    urls_file = os.path.join(UPLOAD_FOLDER, "urls.txt")
    with open(urls_file, "w") as f:
        f.write("\n".join(all_urls))

    return jsonify({"message": "Upload successful!", "urls": all_urls})


@app.route("/view_files", methods=["GET"])
def view_files():
    """View uploaded URLs"""
    urls_file = os.path.join(UPLOAD_FOLDER, "urls.txt")
    
    # Ensure file exists before reading
    if os.path.exists(urls_file):
        with open(urls_file, "r") as f:
            urls = f.read().splitlines()
        return jsonify({"urls": urls})
    
    return jsonify({"message": "No files uploaded yet"}), 400  # Return 400 error if no file



@app.route("/clear_files", methods=["POST"])
def clear_files():
    """Clears uploaded files and URLs."""
    for file in os.listdir(UPLOAD_FOLDER):
        os.remove(os.path.join(UPLOAD_FOLDER, file))
    return jsonify({"message": "All uploaded files cleared"})


@app.route("/start_scraping", methods=["POST"])
def start_scraping():
    """Starts scraping process and generates a GeoJSON file."""
    urls_file = os.path.join(UPLOAD_FOLDER, "urls.txt")
    geojson_file = os.path.join(UPLOAD_FOLDER, "scraped_data.geojson")

    if not os.path.exists(urls_file):
        return jsonify({"error": "No URLs to scrape"}), 400

    with open(urls_file, "r") as f:
        urls = f.read().splitlines()

    features = []
    total_urls = len(urls)

    for index, url in enumerate(urls, start=1):
        venue_name = f"Venue {index}"  # Placeholder name
        lat, lon, address = get_coordinates(venue_name)

        feature = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "url": url,
                "venue_name": venue_name if venue_name != "Unknown Venue" else f"Venue {index}",
                "address": address,
            },
        }
        features.append(feature)

        # Update progress
        progress["value"] = int((index / total_urls) * 100)

    geojson_data = {"type": "FeatureCollection", "features": features}

    with open(geojson_file, "w") as f:
        json.dump(geojson_data, f, indent=4)

    progress["value"] = 100
    return jsonify({"message": "Scraping completed!", "geojson": geojson_file})


@app.route("/progress", methods=["GET"])
def get_progress():
    """Returns current scraping progress"""
    return jsonify({"progress": progress["value"]})


@app.route("/download", methods=["GET"])
def download_geojson():
    """Allows user to download the generated GeoJSON file"""
    geojson_file = os.path.join(UPLOAD_FOLDER, "scraped_data.geojson")
    if os.path.exists(geojson_file):
        return send_file(geojson_file, as_attachment=True)
    return jsonify({"error": "No GeoJSON file found"}), 404


if __name__ == "__main__":
    app.run(debug=True)
