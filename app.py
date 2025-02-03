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
            return [lon, lat]  # Returns actual coordinates
        else:
            print(f"⚠️ No location found for {venue_name}")
            return None  # Skip if location not found
    except Exception as e:
        print("Error fetching coordinates:", e)
        return None

def scrape_urls():
    global scraping_progress
    scraped_data = []
    total_urls = len(uploaded_files)

    if total_urls == 0:
        print("⚠️ No URLs to scrape!")
        return []

    for i, url in enumerate(uploaded_files):
        time.sleep(2)  # Simulate scraping delay

        venue_name = f"Venue {i+1}"  # Placeholder, replace with real venue name
        address = f"Address {i+1}"  # Placeholder, replace with actual address
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
        print(f"✅ Scraping {i+1}/{total_urls}: {url} ({scraping_progress}%)")  

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
    print("Uploaded URLs:", uploaded_files)  
    return jsonify({"message": "File uploaded", "urls": urls})

@app.route("/start_scraping", methods=["POST"])
def start_scraping():
    global scraping_progress
    scraping_progress = 0  

    if not uploaded_files:
        return jsonify({"error": "No files uploaded"}), 400

    scraped_data = scrape_urls()
    geojson_data = {"type": "FeatureCollection", "features": scraped_data}

    geojson_path = os.path.join(UPLOAD_FOLDER, "scraped_data.geojson")
    with open(geojson_path, "w", encoding="utf-8") as geojson_file:
        json.dump(geojson_data, geojson_file, indent=4)

    print("✅ Scraping completed! File ready to download.")
    return jsonify({"message": "Scraping complete", "download_url": "/download"})

@app.route("/progress", methods=["GET"])
def get_progress():
    return jsonify({"progress": scraping_progress})

@app.route("/download")
def download_geojson():
    geojson_path = os.path.join(UPLOAD_FOLDER, "scraped_data.geojson")

    if not os.path.exists(geojson_path):
        return jsonify({"error": "GeoJSON file not found"}), 500
    
    return send_file(geojson_path, as_attachment=True)

@app.route("/clear", methods=["POST"])
def clear_uploaded_files():
    global uploaded_files
    uploaded_files = []
    return jsonify({"message": "Uploaded files cleared"})

if __name__ == "__main__":
    app.run(debug=True)
