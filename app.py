import os
import json
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
import geopandas as gpd
import shapely.geometry
from flask_cors import CORS
import redis

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Allow CORS for frontend interaction

# File Upload Settings
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"txt", "csv", "json"}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Redis Setup (Optional, Only if Used in Your App)
try:
    redis_client = redis.StrictRedis(host=os.getenv("REDIS_URL", "localhost"), port=6379, decode_responses=True)
    redis_client.ping()
    print("✅ Redis Connected")
except redis.exceptions.ConnectionError:
    redis_client = None
    print("🚨 Redis Connection Failed")

# Function to check allowed file types
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload_file():
    print("📥 File Upload Request Received")  # Debugging log

    if "file" not in request.files:
        print("❌ No file in request")
        return jsonify({"message": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "":
        print("❌ No file selected")
        return jsonify({"message": "No file selected"}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(file_path)

        print(f"✅ File saved successfully: {file_path}")
        return jsonify({"message": f"File '{filename}' uploaded successfully"}), 200

    return jsonify({"message": "Invalid file format"}), 400

@app.route("/generate_geojson", methods=["POST"])
def generate_geojson():
    try:
        data = request.json
        print("📌 Received Data for GeoJSON:", data)

        # Generate GeoJSON structure
        geojson_data = {
            "type": "FeatureCollection",
            "features": []
        }

        for item in data.get("locations", []):
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [item["lng"], item["lat"]]
                },
                "properties": {
                    "name": item.get("name", "Unknown Location")
                }
            }
            geojson_data["features"].append(feature)

        # Save to a file
        geojson_path = "polygon.geojson"
        with open(geojson_path, "w") as geojson_file:
            json.dump(geojson_data, geojson_file)

        print("✅ GeoJSON Created Successfully")
        return jsonify({"message": "GeoJSON generated", "geojson_file": geojson_path}), 200

    except Exception as e:
        print("🚨 Error generating GeoJSON:", str(e))
        return jsonify({"error": str(e)}), 500

@app.route("/download_geojson")
def download_geojson():
    geojson_path = "polygon.geojson"
    if os.path.exists(geojson_path):
        return send_file(geojson_path, as_attachment=True)
    return jsonify({"message": "GeoJSON file not found"}), 404

# Run the app
if __name__ == "__main__":
    print("🚀 Starting Flask App...")
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
