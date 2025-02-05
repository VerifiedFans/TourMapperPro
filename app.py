from flask import Flask, render_template, request, send_file, jsonify
import os
import csv
import json
from shapely.geometry import Polygon, mapping
from geopy.geocoders import Nominatim

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
GEOJSON_FILE = 'static/output.geojson'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

geolocator = Nominatim(user_agent="tourmapper-pro")

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file uploaded'})

    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No selected file'})

    filepath = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(filepath)

    process_csv(filepath)

    return jsonify({'success': True})

@app.route('/download')
def download_geojson():
    if os.path.exists(GEOJSON_FILE):
        return send_file(GEOJSON_FILE, as_attachment=True)
    else:
        return "No GeoJSON file available", 404

def process_csv(filepath):
    features = []
    
    with open(filepath, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        
        for row in reader:
            venue_name = row['venue_name']
            address = row['address']
            city = row['city']
            state = row['state']
            zip_code = row['zip']
            full_address = f"{address}, {city}, {state} {zip_code}"

            location = geolocator.geocode(full_address)
            if location:
                latitude, longitude = location.latitude, location.longitude

                # Example polygon (venue footprint)
                venue_polygon = Polygon([
                    (longitude - 0.001, latitude - 0.001),
                    (longitude + 0.001, latitude - 0.001),
                    (longitude + 0.001, latitude + 0.001),
                    (longitude - 0.001, latitude + 0.001),
                    (longitude - 0.001, latitude - 0.001)
                ])

                # Example polygon (parking lot footprint)
                parking_polygon = Polygon([
                    (longitude - 0.002, latitude - 0.002),
                    (longitude + 0.002, latitude - 0.002),
                    (longitude + 0.002, latitude + 0.002),
                    (longitude - 0.002, latitude + 0.002),
                    (longitude - 0.002, latitude - 0.002)
                ])

                features.append({
                    "type": "Feature",
                    "geometry": mapping(venue_polygon),
                    "properties": {"name": venue_name, "type": "venue"}
                })

                features.append({
                    "type": "Feature",
                    "geometry": mapping(parking_polygon),
                    "properties": {"name": venue_name, "type": "parking"}
                })

    geojson_data = {"type": "FeatureCollection", "features": features}

    with open(GEOJSON_FILE, 'w') as geojson_file:
        json.dump(geojson_data, geojson_file, indent=4)

if __name__ == '__main__':
    app.run(debug=True)
