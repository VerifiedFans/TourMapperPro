import json
import os
from flask import Flask, request, send_from_directory, render_template, jsonify

app = Flask(__name__)

# Ensure the 'static' directory exists
STATIC_DIR = "static"
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)

# Temporary storage for URLs
stored_urls = []


# ==============================
# 🔹 Serve Main Page
# ==============================
@app.route("/")
def home():
    return render_template("index.html")


# ==============================
# 🔹 Upload URLs API
# ==============================
@app.route("/upload_urls", methods=["POST"])
def upload_urls():
    global stored_urls
    data = request.json
    urls = data.get("urls", [])
    
    if not urls:
        return jsonify({"error": "No URLs provided"}), 400

    stored_urls.extend(urls)
    return jsonify({"message": "URLs received", "urls": stored_urls})


# ==============================
# 🔹 View Stored URLs (Separate Page)
# ==============================
@app.route("/view_urls", methods=["GET"])
def view_urls():
    return render_template("view_urls.html", urls=stored_urls)


# ==============================
# 🔹 Clear Stored URLs
# ==============================
@app.route("/clear_urls", methods=["POST"])
def clear_urls():
    global stored_urls
    stored_urls = []
    return jsonify({"message": "URLs cleared"})


# ==============================
# 🔹 Generate & Serve GeoJSON File
# ==============================
def generate_geojson():
    geojson_data = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[-73.98, 40.75], [-73.99, 40.76], [-74.00, 40.77], [-73.98, 40.75]]
                    ]
                },
                "properties": {"name": "Example Polygon"}
            }
        ]
    }
    with open(f"{STATIC_DIR}/events.geojson", "w") as f:
        json.dump(geojson_data, f)


# ==============================
# 🔹 Generate & Serve KML File
# ==============================
def generate_kml():
    kml_data = """<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
      <Placemark>
        <name>Sample Location</name>
        <Polygon>
          <outerBoundaryIs>
            <LinearRing>
              <coordinates>-73.98,40.75 -73.99,40.76 -74.00,40.77 -73.98,40.75</coordinates>
            </LinearRing>
          </outerBoundaryIs>
        </Polygon>
      </Placemark>
    </kml>"""
    with open(f"{STATIC_DIR}/events.kml", "w") as f:
        f.write(kml_data)


# ==============================
# 🔹 Start Scraping (Generate GeoJSON & KML)
# ==============================
@app.route("/start_scraping", methods=["POST"])
def start_scraping():
    generate_geojson()
    generate_kml()
    return jsonify({"message": "Scraping completed & files updated."}), 200


# ==============================
# 🔹 Serve Static Files (GeoJSON & KML)
# ==============================
@app.route("/static/<path:filename>")
def serve_static(filename):
    return send_from_directory(STATIC_DIR, filename)


# ==============================
# 🔹 Run Flask App
# ==============================
if __name__ == "__main__":
    app.run(debug=True)
