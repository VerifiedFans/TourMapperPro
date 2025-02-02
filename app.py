import os
import json
import logging
import requests
from flask import Flask, render_template, request, jsonify, send_from_directory

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
GEOJSON_FOLDER = "static"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(GEOJSON_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["GEOJSON_FOLDER"] = GEOJSON_FOLDER

logging.basicConfig(level=logging.INFO)

# OpenStreetMap Overpass API for venue location
def get_coordinates(venue_name):
    url = "https://overpass-api.de/api/interpreter"
    query = f"""
    [out:json];
    node["name"="{venue_name}"];
    out center;
    """
    response = requests.get(url, params={"data": query})
    data = response.json()

    if "elements" in data and len(data["elements"]) > 0:
        lat = data["elements"][0]["lat"]
        lon = data["elements"][0]["lon"]
        return lon, lat
    return None

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    filepath = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
    file.save(filepath)
    return jsonify({"message": f"File '{file.filename}' uploaded successfully!"})

@app.route("/view_files", methods=["GET"])
def view_files():
    files = os.listdir(app.config["UPLOAD_FOLDER"])
    return jsonify({"files": files})

@app.route("/clear_files", methods=["POST"])
def clear_files():
    try:
        folder = app.config["UPLOAD_FOLDER"]
        for file in os.listdir(folder):
            os.remove(os.path.join(folder, file))
        return jsonify({"message": "All uploaded files cleared!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/start_scraping", methods=["POST"])
def start_scraping():
    uploaded_files = os.listdir(app.config["UPLOAD_FOLDER"])
    if not uploaded_files:
        return jsonify({"error": "No files to process"}), 400

    geojson_data = {"type": "FeatureCollection", "features": []}

    for filename in uploaded_files:
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        with open(filepath, "r") as f:
            urls = f.read().splitlines()

        for url in urls:
            venue_name = url.split("/")[-1]  
            coordinates = get_coordinates(venue_name)

            if coordinates:
                lon, lat = coordinates
            else:
                lon, lat = 0, 0 

            geojson_data["features"].append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {"url": url, "venue": venue_name, "type": "venue"}
            })

    geojson_path = os.path.join(app.config["GEOJSON_FOLDER"], "events.geojson")
    with open(geojson_path, "w") as geojson_file:
        json.dump(geojson_data, geojson_file, indent=4)

    return jsonify({"message": "Scraping completed!", "geojson_file": "events.geojson"})

@app.route("/download_geojson")
def download_geojson():
    return send_from_directory(app.config["GEOJSON_FOLDER"], "events.geojson", as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
