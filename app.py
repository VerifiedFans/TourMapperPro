from flask import Flask, render_template, request, jsonify
import json
import os

app = Flask(__name__)

# ✅ Store uploaded URLs
uploaded_urls = []

@app.route("/")
def home():
    return render_template("index.html")

# ✅ Endpoint to Upload URLs
@app.route("/upload_urls", methods=["POST"])
def upload_urls():
    global uploaded_urls
    data = request.get_json()
    uploaded_urls = data.get("urls", [])
    
    if not uploaded_urls:
        return jsonify({"error": "No URLs provided"}), 400
    
    return jsonify({"message": f"Uploaded {len(uploaded_urls)} URLs successfully!"})

# ✅ Endpoint to Start Scraping
@app.route("/start_scraping", methods=["POST"])
def start_scraping():
    global uploaded_urls

    if not uploaded_urls:
        return jsonify({"error": "No URLs uploaded. Please upload first."}), 400

    geojson_data = {
        "type": "FeatureCollection",
        "features": []
    }

    for url in uploaded_urls:
        # 🎯 Simulating lat/lon extraction (Replace with actual scraping logic)
        lat, lon = 40.7128, -74.0060  # Example lat/lon for testing
        geojson_data["features"].append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [lon, lat]
            },
            "properties": {
                "url": url,
                "type": "venue"
            }
        })

    # ✅ Save GeoJSON file
    with open("static/events.geojson", "w") as f:
        json.dump(geojson_data, f, indent=4)

    return jsonify({"message": "Scraping completed! Download the GeoJSON file."})

if __name__ == "__main__":
    app.run(debug=True)

