
from flask import Flask, request, jsonify, render_template, send_file
import os
import csv
import json
import time
import requests

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

uploaded_files = []
scraping_progress = 0

def get_coordinates(venue_name):
    API_URL = f"https://nominatim.openstreetmap.org/search?q={venue_name}&format=json"

    try:
        response = requests.get(API_URL)
        data = response.json()

        if data:
            lat = float(data[0]["lat"])
            lon = float(data[0]["lon"])
            return [lon, lat]  # Return actual location
        else:
            return None  # Return None if no valid location found
    except Exception as e:
        print("Error fetching coordinates:", e)
        return None

def scrape_urls(urls):
    global scraping_progress
    scraped_data = []
    total_urls = len(urls)

    for i, url in enumerate(urls):
        time.sleep(1)  # Simulate scraping delay

        venue_name = f"Venue {i+1}"
        address = f"Address {i+1}"
        coordinates = get_coordinates(venue_name)

        if coordinates is None:
            continue  # Skip if location is not found

        scraped_data.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": coordinates},
            "properties": {
                "url": url,
                "venue_name": venue_name,
                "address": address
            }
        })

        scraping_progress = int(((i + 1) / total_urls) * 100)

    return scraped_data

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload_file():
    global uploaded_files
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(file_path)

    urls = []
    if file.filename.endswith(".csv"):
        with open(file_path, newline="", encoding="utf-8") as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                urls.append(row[0])  
    elif file.filename.endswith(".txt"):
        with open(file_path, "r", encoding="utf-8") as txtfile:
            urls = txtfile.read().splitlines()

    uploaded_files.extend(urls)
    return jsonify({"message": "File uploaded", "urls": urls})

@app.route("/paste_urls", methods=["POST"])
def paste_urls():
    global uploaded_files
    data = request.get_json()
    urls = data.get("urls", [])
    uploaded_files.extend(urls)
    return jsonify({"message": "Pasted URLs added!"})

@app.route("/uploaded_urls", methods=["GET"])
def get_uploaded_urls():
    return jsonify({"urls": uploaded_files})

@app.route("/clear", methods=["POST"])
def clear_uploaded_files():
    global uploaded_files
    uploaded_files = []
    return jsonify({"message": "Uploaded files cleared"})

@app.route("/progress", methods=["GET"])
def get_progress():
    return jsonify({"progress": scraping_progress})

@app.route("/start_scraping", methods=["POST"])
def start_scraping():
    global scraping_progress
    scraping_progress = 0

    if not uploaded_files:
        return jsonify({"error": "No files uploaded"}), 400

    scraped_data = scrape_urls(uploaded_files)
    geojson_data = {"type": "FeatureCollection", "features": scraped_data}

    geojson_path = os.path.join(UPLOAD_FOLDER, "scraped_data.geojson")
    with open(geojson_path, "w", encoding="utf-8") as geojson_file:
        json.dump(geojson_data, geojson_file, indent=4)

    return jsonify({"message": "Scraping complete", "download_url": "/download"})

@app.route("/download")
def download_geojson():
    geojson_path = os.path.join(UPLOAD_FOLDER, "scraped_data.geojson")

    if not os.path.exists(geojson_path):
        return jsonify({"error": "GeoJSON file not found"}), 500
    
    return send_file(geojson_path, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)
