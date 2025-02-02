import os
import json
import logging
from flask import Flask, render_template, request, jsonify, send_from_directory

UPLOAD_FOLDER = "uploads"
STATIC_FOLDER = "static"
LOGO_FILE = "logo.png"  # Ensure logo is in `static/` folder

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(STATIC_FOLDER, exist_ok=True)

logging.basicConfig(level=logging.INFO)


@app.route("/")
def home():
    """Serve the main page."""
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload_file():
    """Handles file uploads."""
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(file_path)

    return jsonify({"message": f"Uploaded {file.filename} successfully"})


@app.route("/view_uploaded_files", methods=["GET"])
def view_uploaded_files():
    """Returns a list of uploaded files"""
    files = os.listdir(UPLOAD_FOLDER)
    return jsonify({"files": files})


@app.route("/clear_urls", methods=["POST"])
def clear_urls():
    """Deletes all uploaded files"""
    for file in os.listdir(UPLOAD_FOLDER):
        os.remove(os.path.join(UPLOAD_FOLDER, file))
    return jsonify({"message": "All uploaded URLs have been cleared"})


@app.route("/generate_geojson", methods=["POST"])
def generate_geojson():
    """Processes uploaded files & creates a GeoJSON file."""
    geojson_data = {"type": "FeatureCollection", "features": []}

    for filename in os.listdir(UPLOAD_FOLDER):
        file_path = os.path.join(UPLOAD_FOLDER, filename)

        with open(file_path, "r") as f:
            lines = f.readlines()

        for line in lines:
            line = line.strip()
            if line:
                # Example: Use OpenStreetMap Overpass API to fetch venue locations
                coordinates = [-74.006, 40.7128]  # Mocked (Replace with real lat/lon)
                geojson_data["features"].append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": coordinates},
                    "properties": {"url": line, "type": "venue"},
                })

    geojson_path = os.path.join(STATIC_FOLDER, "events.geojson")
    with open(geojson_path, "w") as geojson_file:
        json.dump(geojson_data, geojson_file, indent=4)

    return jsonify({"message": "GeoJSON created!", "file": "events.geojson"})


@app.route("/static/<path:filename>")
def serve_static(filename):
    """Serve static files (e.g., GeoJSON, logo)."""
    return send_from_directory(STATIC_FOLDER, filename)


if __name__ == "__main__":
    app.run(debug=True)

