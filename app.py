from flask import Flask, render_template, request, jsonify, send_file
import json
import os

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Venue & Parking Sample Coordinates
venue_coords = {"lat": 40.7505045, "lng": -73.9934387}
parking_coords = {"lat": 40.7488933, "lng": -73.9899767}

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"message": "No file uploaded"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"message": "No file selected"}), 400

    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(file_path)
    
    return jsonify({"message": f"File '{file.filename}' uploaded successfully"}), 200

@app.route('/get_geojson')
def get_geojson():
    """ Generate GeoJSON dynamically and return it """
    polygon_points = [
        [venue_coords["lng"], venue_coords["lat"]],
        [parking_coords["lng"], parking_coords["lat"]],
        [venue_coords["lng"] + 0.001, venue_coords["lat"] - 0.001],
        [parking_coords["lng"] - 0.001, parking_coords["lat"] + 0.001],
    ]

    geojson_data = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [polygon_points]
                },
                "properties": {
                    "name": "Venue and Parking Area"
                }
            }
        ]
    }

    # Save GeoJSON to a file
    with open("polygon.geojson", "w") as f:
        json.dump(geojson_data, f)

    return jsonify(geojson_data)

@app.route('/download_geojson')
def download_geojson():
    """ Send the GeoJSON file for download """
    return send_file("polygon.geojson", as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
