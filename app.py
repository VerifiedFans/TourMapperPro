import os
from flask import Flask, render_template, request, jsonify, send_from_directory

app = Flask(__name__)

# ✅ Ensure the static directory exists
STATIC_DIR = os.path.join(app.root_path, "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)

# ✅ In-memory storage for uploaded URLs (temporary solution)
uploaded_urls = []

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
    global uploaded_urls
    data = request.json
    urls = data.get("urls", [])
    if not urls:
        return jsonify({"error": "No URLs provided"}), 400
    uploaded_urls.extend(urls)  # Append new URLs to the list
    return jsonify({"message": "URLs received", "urls": uploaded_urls})

# ✅ View uploaded URLs API
@app.route("/view_urls", methods=["GET"])
def view_urls():
    return jsonify({"uploaded_urls": uploaded_urls})

# ✅ Clear uploaded URLs API
@app.route("/clear_urls", methods=["POST"])
def clear_urls():
    global uploaded_urls
    uploaded_urls = []  # Reset the list
    return jsonify({"message": "All URLs cleared"})

# ✅ Start scraping API (Dummy Response)
@app.route("/start_scraping", methods=["POST"])
def start_scraping():
    return jsonify({"message": "Scraping started"}), 200

# ✅ Run the Flask app on the correct port for Heroku
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Heroku requires dynamic port binding
    app.run(host="0.0.0.0", port=port, debug=True)
