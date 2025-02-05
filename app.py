from flask import Flask, render_template, request, Response, jsonify, send_file
import time
import os
import pandas as pd
import json
from shapely.geometry import Polygon, mapping

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "geojsons"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    filename = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(filename)

    def generate_progress():
        for i in range(1, 101):  # Simulate progress from 1% to 100%
            time.sleep(0.05)  # Simulate processing
            yield f"data:{i}\n\n"

        process_file(filename)  # Process CSV & generate GeoJSON
        yield f"data:complete\n\n"

    return Response(generate_progress(), mimetype='text/event-stream')

def process_file(csv_path):
    """Processes the CSV and generates a GeoJSON file."""
    df = pd.read_csv(csv_path)
    features = []

    for _, row in df.iterrows():
        lat, lon = row['Latitude'], row['Longitude']
        polygon = Polygon([
            (lon - 0.001, lat - 0.001),
            (lon + 0.001, lat - 0.001),
            (lon + 0.001, lat + 0.001),
            (lon - 0.001, lat + 0.001),
            (lon - 0.001, lat - 0.001)
        ])
        
        feature = {
            "type": "Feature",
            "geometry": mapping(polygon),
            "properties": {"name": row['Venue']}
        }
        features.append(feature)

    geojson_data = {"type": "FeatureCollection", "features": features}
    output_filename = os.path.join(OUTPUT_FOLDER, "venues.geojson")

    with open(output_filename, "w") as geojson_file:
        json.dump(geojson_data, geojson_file)

@app.route('/download')
def download_file():
    """Provides the GeoJSON file for download."""
    file_path = os.path.join(OUTPUT_FOLDER, "venues.geojson")
    return send_file(file_path, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
