import os
import json
import logging
from flask import Flask, render_template, request, jsonify, send_from_directory

app = Flask(__name__)

# Configuration
UPLOAD_FOLDER = "uploads"
GEOJSON_FOLDER = "static"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)  # Ensure folders exist
os.makedirs(GEOJSON_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["GEOJSON_FOLDER"] = GEOJSON_FOLDER

# Enable logging
logging.basicConfig(level=logging.INFO)

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
            geojson_data["features"].append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-74.006, 40.7128]},  # Example coordinates
                "properties": {"url": url, "type": "venue"}
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
