import os
import json
import requests
from flask import Flask, request, jsonify, send_file

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

API_KEY = AIzaSyC-3B4JggRvgZFHpgN7JfYJqjidhtKo-cE  # 🔹 Replace with your actual API key


def get_coordinates(venue_name):
    """Retrieve latitude, longitude, and address from Google Maps API"""
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={venue_name}&key={API_KEY}"
    response = requests.get(url)

    print(f"📡 API Request URL: {url}")  # 🔍 Debugging: Show API request
    print(f"🌍 API Response: {response.text}")  # 🔍 Debugging: Show API response

    try:
        data = response.json()
        if "results" in data and len(data["results"]) > 0:
            location = data["results"][0]["geometry"]["location"]
            formatted_address = data["results"][0]["formatted_address"]
            return location["lat"], location["lng"], formatted_address

    except Exception as e:
        print(f"❌ API Error: {e}")

    return None, None, "Unknown Address"  # 🔹 Return safe defaults


@app.route("/upload", methods=["POST"])
def upload_file():
    """Upload URLs via file or text input"""
    if "file" not in request.files and "urls" not in request.form:
        return jsonify({"error": "No file or text data provided"}), 400

    urls = []

    # File upload
    if "file" in request.files:
        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "No file selected"}), 400
        urls = file.read().decode("utf-8").splitlines()

    # Text input
    if "urls" in request.form:
        urls += request.form["urls"].splitlines()

    urls = [url.strip() for url in urls if url.strip()]

    if not urls:
        return jsonify({"error": "No valid URLs found"}), 400

    # Save to file
    urls_file = os.path.join(UPLOAD_FOLDER, "urls.txt")
    with open(urls_file, "w") as f:
        for url in urls:
            f.write(url + "\n")

    print("📄 Saved URLs in urls.txt:")  # Debugging
    with open(urls_file, "r") as f:
        print(f.read())

    return jsonify({"message": "URLs uploaded successfully", "count": len(urls)})


@app.route("/view_files", methods=["GET"])
def view_files():
    """View uploaded URLs"""
    urls_file = os.path.join(UPLOAD_FOLDER, "urls.txt")

    if os.path.exists(urls_file):
        with open(urls_file, "r") as f:
            urls = f.read().splitlines()

        print("👀 Viewing URLs from urls.txt:")  # Debugging
        print(urls)

        return jsonify({"urls": urls})

    return jsonify({"message": "No files uploaded yet"}), 400


@app.route("/start_scraping", methods=["POST"])
def start_scraping():
    """Scrape URLs and generate GeoJSON file"""
    urls_file = os.path.join(UPLOAD_FOLDER, "urls.txt")

    if not os.path.exists(urls_file):
        return jsonify({"error": "No URLs found. Please upload URLs first."}), 400

    # Read URLs from file
    with open(urls_file, "r") as f:
        urls = f.read().splitlines()

    features = []

    for url in urls:
        venue_name = extract_venue_name(url)  # Extract name from URL
        lat, lon, address = get_coordinates(venue_name)

        # 🔹 If geocoding fails, keep processing with default values
        if lat is None or lon is None:
            lat, lon = -74.006, 40.7128  # Default to New York
            print(f"⚠️ Could not find coordinates for {venue_name}. Using default.")

        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {
                    "url": url,
                    "venue_name": venue_name or "Unknown Venue",
                    "address": address,
                },
            }
        )

    geojson_data = {"type": "FeatureCollection", "features": features}

    # Save as GeoJSON file
    geojson_path = os.path.join(UPLOAD_FOLDER, "scraped_data.geojson")
    with open(geojson_path, "w") as f:
        json.dump(geojson_data, f, indent=2)

    print(f"✅ GeoJSON file saved at {geojson_path}")

    return jsonify({"message": "Scraping completed, GeoJSON file ready for download"})


@app.route("/download", methods=["GET"])
def download_geojson():
    """Download the generated GeoJSON file"""
    geojson_path = os.path.join(UPLOAD_FOLDER, "scraped_data.geojson")

    if not os.path.exists(geojson_path):
        return jsonify({"error": "GeoJSON file not found. Please scrape first."}), 400

    return send_file(geojson_path, as_attachment=True)


def extract_venue_name(url):
    """Extract venue name from URL (simplified)"""
    parts = url.split("/")
    for part in parts:
        if "bandsintown" in part:
            continue  # Ignore base URL
        return part.replace("-", " ").title()  # Convert dashes to spaces
    return "Unknown Venue"


if __name__ == "__main__":
    app.run(debug=True)
