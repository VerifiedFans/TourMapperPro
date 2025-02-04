from flask import Flask, render_template, request, jsonify, send_file
import time  # Simulate scraping delay
import json
import os

app = Flask(__name__)

# Save directory for GeoJSON
SAVE_DIR = "static"
os.makedirs(SAVE_DIR, exist_ok=True)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/process-urls", methods=["POST"])
def process_urls():
    data = request.get_json()
    urls = data.get("urls", [])

    if not urls:
        return jsonify({"message": "No URLs provided."}), 400

    results = []
    for url in urls:
        time.sleep(1)  # Simulated scraping delay
        venue_name = f"Venue {len(results) + 1}"  # Dummy venue name
        geojson_data = {
            "type": "Feature",
            "properties": {
                "name": venue_name,
                "address": "123 Example St",
                "city": "Somewhere",
                "state": "CA",
                "zip": "12345",
                "date": "2025-02-04"
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[-122.4, 37.8], [-122.4, 37.81], [-122.39, 37.81], [-122.39, 37.8], [-122.4, 37.8]]
                ]
            }
        }
        results.append(geojson_data)

    # Save to GeoJSON file
    geojson_file = os.path.join(SAVE_DIR, "events.geojson")
    with open(geojson_file, "w") as f:
        json.dump({"type": "FeatureCollection", "features": results}, f, indent=2)

    return jsonify({"message": "Scraping Complete!", "urls": urls, "download_url": "/static/events.geojson"})

@app.route("/download")
def download():
    return send_file("static/events.geojson", as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)
