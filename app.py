import os
from flask import Flask, render_template, send_from_directory, request, jsonify
import googlemaps

app = Flask(__name__)

# Load API key from environment variables
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

# Check if API key is set
if not GOOGLE_MAPS_API_KEY:
    raise ValueError("Invalid API key provided.")

# Initialize Google Maps Client
gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

# Serve homepage
@app.route("/")
def home():
    return render_template("index.html", api_key=GOOGLE_MAPS_API_KEY)

# Serve static files (GeoJSON & KML)
@app.route("/static/<path:filename>")
def serve_static(filename):
    static_dir = os.path.join(app.root_path, "static")
    return send_from_directory(static_dir, filename)

# API to receive uploaded URLs
@app.route("/upload_urls", methods=["POST"])
def upload_urls():
    data = request.json
    urls = data.get("urls", [])
    if not urls:
        return jsonify({"error": "No URLs provided"}), 400
    return jsonify({"message": "URLs received", "urls": urls})

# Start scraping process (placeholder function)
@app.route("/start_scraping", methods=["POST"])
def start_scraping():
    return jsonify({"message": "Scraping started"}), 200

if __name__ == "__main__":
    app.run(debug=True)
