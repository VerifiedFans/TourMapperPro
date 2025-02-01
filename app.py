import os
import json
import googlemaps
import requests
from flask import Flask, request, jsonify, render_template, send_from_directory

app = Flask(__name__)

# Load API key from environment variable
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

# Store uploaded venues and URLs
venues = []
uploaded_urls = []


@app.route("/")
def home():
    return render_template("index.html")


# 📌 1. Upload URLs Endpoint (Fixed)
@app.route("/upload_urls", methods=["POST"])
def upload_urls():
    """Receives URLs from the client and stores them"""
    data = request.get_json()
    urls = data.get("urls", [])

    if not urls:
        return jsonify({"error": "No URLs provided"}), 400

    uploaded_urls.extend(urls)  # Append to list
    return jsonify({"message": "URLs uploaded successfully", "urls": uploaded_urls})


# 📌 2. View Uploaded URLs in a Separate Page
@app.route("/view_urls")
def view_urls():
    return render_template("view_urls.html", urls=uploaded_urls)


# 📌 3. Clear Uploaded URLs
@app.route("/clear_urls", methods=["POST"])
def clear_urls():
    """Clears stored URLs"""
    uploaded_urls.clear()
    return jsonify({"message": "URLs cleared successfully"})


# 📌 4. Generate GeoJSON File
@app.route("/generate_geojson", methods=["GET"])
def generate_geojson():
    if not venues:
        return jsonify({"error": "No venues stored"}), 404

    geojson = {
        "type": "FeatureCollection",
        "features": []
    }

    for venue in venues:
        lat, lon = venue["lat"], venue["lon"]
        geojson["features"].append({
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [lon + 0.001, lat + 0.001],
                    [lon - 0.001, lat + 0.001],
                    [lon - 0.001, lat - 0.001],
                    [lon + 0.001, lat - 0.001],
                    [lon + 0.001, lat + 0.001]
                ]]
            },
            "properties": {
                "name": venue["name"]
            }
        })

    static_dir = os.path.join(app.root_path, "static")
    geojson_path = os.path.join(static_dir, "events.geojson")

    with open(geojson_path, "w") as f:
        json.dump(geojson, f)

    return jsonify({"message": "GeoJSON generated", "file": "/static/events.geojson"})


# 📌 5. Serve Static Files (GeoJSON & KML)
@app.route("/static/<path:filename>")
def serve_static(filename):
    static_dir = os.path.join(app.root_path, "static")
    return send_from_directory(static_dir, filename)


if __name__ == "__main__":
    app.run(debug=True)
