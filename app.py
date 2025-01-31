from flask import Flask, send_from_directory, request, jsonify
import os

app = Flask(__name__)

# Ensure static folder exists
STATIC_FOLDER = os.path.join(app.root_path, "static")
if not os.path.exists(STATIC_FOLDER):
    os.makedirs(STATIC_FOLDER)

# Serve static files (KML & GeoJSON)
@app.route("/static/<path:filename>")
def serve_static(filename):
    return send_from_directory(STATIC_FOLDER, filename)

# Homepage Route
@app.route("/")
def home():
    return "🚀 Flask App is Running on Heroku!"

# Upload URLs API (Dummy Example)
@app.route("/upload_urls", methods=["POST"])
def upload_urls():
    data = request.json
    urls = data.get("urls", [])
    if not urls:
        return jsonify({"error": "No URLs provided"}), 400
    return jsonify({"message": "URLs received", "urls": urls})

# Start scraping process API (Dummy Example)
@app.route("/start_scraping", methods=["POST"])
def start_scraping():
    return jsonify({"message": "Scraping started"}), 200

# Run the app
if __name__ == "__main__":
    app.run(debug=True)
