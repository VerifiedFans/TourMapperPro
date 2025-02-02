
from flask import Flask, request, jsonify, render_template, send_file
import os
import csv
import json
import time  # Simulates progress bar updates

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

uploaded_files = []  # Stores uploaded URLs

# Function to simulate scraping (replace with actual scraping logic)
def scrape_urls(urls):
    scraped_data = []
    for i, url in enumerate(urls):
        time.sleep(1)  # Simulate scraping delay
        scraped_data.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-74.006, 40.7128]},  # Replace with actual coordinates
            "properties": {"url": url, "venue_name": "Sample Venue", "address": "123 Main St, NY"}
        })
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

    # Process CSV/TXT and extract URLs
    urls = []
    if file.filename.endswith(".csv"):
        with open(file_path, newline="", encoding="utf-8") as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                urls.append(row[0])  # Assuming URLs are in the first column
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

@app.route("/start_scraping", methods=["POST"])
def start_scraping():
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
    return send_file(geojson_path, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)
