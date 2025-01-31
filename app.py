import os
import json
from flask import Flask, render_template, request, jsonify, send_from_directory

app = Flask(__name__)

# ✅ Ensure 'static' directory exists to store files
STATIC_DIR = os.path.join(app.root_path, "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)

# ✅ Temporary storage for uploaded URLs
uploaded_urls = []

# ✅ Serve static files (KML & GeoJSON)
@app.route("/static/<path:filename>")
def serve_static(filename):
    return send_from_directory(STATIC_DIR, filename)

# ✅ Home Route
@app.route("/")
def home():
    return render_template("index.html")

# ✅ Upload URLs API
@app.route("/upload_urls", methods=["POST"])
def upload_urls():
    global uploaded_urls
    data = request.json
    urls = data.get("urls", [])
    if not urls:
        return jsonify({"error": "No URLs provided"}), 400
    uploaded_urls.extend(urls)
    return jsonify({"message": "URLs received", "urls": uploaded_urls})

# ✅ View Stored URLs in a Separate Window
@app.route("/view_urls", methods=["GET"])
def view_urls():
    return render_template("view_urls.html", urls=uploaded_urls)

# ✅ Clear Uploaded URLs API
@app.route("/clear_urls", methods=["POST"])
def clear_urls():
    global uploaded_urls
    uploaded_urls = []
    return jsonify({"message": "All URLs cleared"})

# ✅ Start Scraping (Placeholder API)
@app.route("/start_scraping", methods=["POST"])
def start_scraping():
    return jsonify({"message": "Scraping started"}), 200

# ✅ Generate Correct GeoJSON Polygon File
@app.route("/generate_geojson", methods=["POST"])
def generate_geojson():
    geojson_data = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [-122.084, 37.422],
                            [-122.084, 37.423],
                            [-122.083, 37.423],
                            [-122.083, 37.422],
                            [-122.084, 37.422]  # Closed loop
                        ]
                    ]
                },
                "properties": {"name": "Example Polygon"}
            }
        ]
    }

    geojson_path = os.path.join(STATIC_DIR, "events.geojson")
    with open(geojson_path, "w") as f:
        json.dump(geojson_data, f)

    return jsonify({"message": "GeoJSON file created", "file": "events.geojson"})

# ✅ Generate Proper KML File
@app.route("/generate_kml", methods=["POST"])
def generate_kml():
    kml_content = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
    <Document>
        <Placemark>
            <name>Sample Polygon</name>
            <Polygon>
                <outerBoundaryIs>
                    <LinearRing>
                        <coordinates>
                            -122.084,37.422,0
                            -122.084,37.423,0
                            -122.083,37.423,0
                            -122.083,37.422,0
                            -122.084,37.422,0
                        </coordinates>
                    </LinearRing>
                </outerBoundaryIs>
            </Polygon>
        </Placemark>
    </Document>
</kml>"""

    kml_path = os.path.join(STATIC_DIR, "events.kml")
    with open(kml_path, "w") as f:
        f.write(kml_content)

    return jsonify({"message": "KML file created", "file": "events.kml"})

# ✅ Ensure the app runs properly on Heroku
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
