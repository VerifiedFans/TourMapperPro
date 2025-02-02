import os
import json
import logging
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# ✅ Enable logging
logging.basicConfig(level=logging.INFO)

UPLOAD_FOLDER = "uploads"
GEOJSON_FILE = "static/events.geojson"

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# ✅ Serve the main page
@app.route("/")
def home():
    return render_template("index.html")

# ✅ Upload URL file (TXT or CSV)
@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(file_path)

    return jsonify({"message": "File uploaded successfully", "filename": file.filename})

# ✅ View Uploaded URLs
@app.route("/view_urls", methods=["GET"])
def view_urls():
    files = os.listdir(UPLOAD_FOLDER)
    urls = []
    for file in files:
        file_path = os.path.join(UPLOAD_FOLDER, file)
        with open(file_path, "r") as f:
            urls.extend(f.read().splitlines())

    return jsonify({"urls": urls})

# ✅ Clear Uploaded URLs
@app.route("/clear_urls", methods=["POST"])
def clear_urls():
    for file in os.listdir(UPLOAD_FOLDER):
        os.remove(os.path.join(UPLOAD_FOLDER, file))
    return jsonify({"message": "All uploaded URLs have been cleared"})

# ✅ Generate and Download GeoJSON
@app.route("/download_geojson", methods=["GET"])
def download_geojson():
    geojson_data = {
        "type": "FeatureCollection",
        "features": []
    }

    # Example: Adding dummy venue location
    geojson_data["features"].append({
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [-74.006, 40.7128]},
        "properties": {"type": "venue", "name": "Sample Venue"}
    })

    with open(GEOJSON_FILE, "w") as f:
        json.dump(geojson_data, f, indent=4)

    return jsonify({"message": "GeoJSON file generated", "file_url": GEOJSON_FILE})

if __name__ == "__main__":
    app.run(debug=True)

