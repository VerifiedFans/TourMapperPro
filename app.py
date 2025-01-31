import os
from flask import Flask, render_template, request, jsonify, send_from_directory

app = Flask(__name__)

# ✅ Ensure the static directory exists
STATIC_DIR = os.path.join(app.root_path, "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)

# ✅ Serve static KML & GeoJSON files
@app.route("/static/<path:filename>")
def serve_static(filename):
    return send_from_directory(STATIC_DIR, filename)

# ✅ Home route (loads a template)
@app.route("/")
def home():
    return render_template("index.html")  # Ensure you have templates/index.html

# ✅ Upload URLs API
@app.route("/upload_urls", methods=["POST"])
def upload_urls():
    data = request.json
    urls = data.get("urls", [])
    if not urls:
        return jsonify({"error": "No URLs provided"}), 400
    return jsonify({"message": "URLs received", "urls": urls})

# ✅ Start scraping API
@app.route("/start_scraping", methods=["POST"])
def start_scraping():
    return jsonify({"message": "Scraping started"}), 200

# ✅ Run the Flask app
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Required for Heroku deployment
    app.run(host="0.0.0.0", port=port, debug=True)
