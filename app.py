from flask import Flask, request, jsonify, send_file, Response
from flask_sse import sse
import time
import csv
import json
import os
import redis

app = Flask(__name__)
app.config["REDIS_URL"] = "redis://localhost:6379"
app.register_blueprint(sse, url_prefix='/events')

UPLOAD_FOLDER = "uploads"
GEOJSON_FOLDER = "geojsons"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(GEOJSON_FOLDER, exist_ok=True)

# Simulated Venue & Parking footprint collection (Replace with actual logic)
def get_venue_footprint(address):
    """Simulate getting a venue footprint based on address."""
    return {
        "type": "Polygon",
        "coordinates": [[
            [0, 0], [0.01, 0], [0.01, 0.01], [0, 0.01], [0, 0]
        ]]
    }

def get_parking_lot_footprint(address):
    """Simulate getting a parking lot footprint near the venue."""
    return {
        "type": "Polygon",
        "coordinates": [[
            [0.02, 0.02], [0.03, 0.02], [0.03, 0.03], [0.02, 0.03], [0.02, 0.02]
        ]]
    }

@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"status": "failed", "message": "No file part"}), 400
    
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"status": "failed", "message": "No selected file"}), 400
    
    filepath = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(filepath)

    geojson_data = {"type": "FeatureCollection", "features": []}

    # Read CSV file and process venue & parking footprints
    try:
        with open(filepath, "r", newline='', encoding="utf-8") as csvfile:
            reader = csv.reader(csvfile)
            headers = next(reader)  # Get column names

            # Ensure address column exists
            if len(headers) == 0:
                return jsonify({"status": "failed", "message": "CSV file appears empty!"}), 400

            total_rows = sum(1 for _ in reader)
            csvfile.seek(0)  # Reset file pointer
            next(reader)  # Skip header again

            for i, row in enumerate(reader, start=1):
                if len(row) == 0:
                    continue  # Skip empty lines

                address = row[0]  # Assume first column is the venue address
                venue_polygon = get_venue_footprint(address)
                parking_polygon = get_parking_lot_footprint(address)

                geojson_data["features"].append({
                    "type": "Feature",
                    "properties": {"name": f"Venue {i}", "address": address},
                    "geometry": venue_polygon
                })
                geojson_data["features"].append({
                    "type": "Feature",
                    "properties": {"name": f"Parking {i}", "address": address},
                    "geometry": parking_polygon
                })

                # Send progress update
                progress = int((i / total_rows) * 100)
                sse.publish({"progress": progress}, type="progress")
                time.sleep(0.2)  # Simulate processing delay

        # Save GeoJSON
        geojson_path = os.path.join(GEOJSON_FOLDER, "venues_parking.geojson")
        with open(geojson_path, "w", encoding="utf-8") as geojson_file:
            json.dump(geojson_data, geojson_file, indent=4)

        return jsonify({"status": "completed", "message": "Upload successful!"})

    except Exception as e:
        return jsonify({"status": "failed", "message": f"Error processing file: {str(e)}"}), 500

@app.route("/progress")
def progress():
    return Response(sse, mimetype="text/event-stream")

@app.route("/download")
def download_file():
    geojson_path = os.path.join(GEOJSON_FOLDER, "venues_parking.geojson")
    if os.path.exists(geojson_path):
        return send_file(geojson_path, as_attachment=True)
    return jsonify({"status": "failed", "message": "No GeoJSON file available"}), 404

if __name__ == "__main__":
    app.run(debug=True)
