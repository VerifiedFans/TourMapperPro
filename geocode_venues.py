from flask import Flask, request, render_template, send_file
import pandas as pd
import os
import json
from shapely.geometry import Point, Polygon, mapping

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
PROCESSED_FOLDER = "processed"

# Only create the folders if they don't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

if not os.path.exists(PROCESSED_FOLDER):
    os.makedirs(PROCESSED_FOLDER)


# Function to create a polygon around a venue
def create_polygon(lat, lon, size=0.001):
    return Polygon([
        (lon - size, lat - size),
        (lon + size, lat - size),
        (lon + size, lat + size),
        (lon - size, lat + size),
        (lon - size, lat - size)
    ])

@app.route("/", methods=["GET", "POST"])
def upload_file():
    if request.method == "POST":
        # Get uploaded file
        file = request.files["file"]
        if file:
            filepath = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(filepath)

            # Process CSV file
            data = pd.read_csv(filepath)

            # Generate GeoJSON
            features = []
            for _, row in data.iterrows():
                lat, lon = row["Latitude"], row["Longitude"]
                venue_name = row["VENUE"]
                polygon = create_polygon(lat, lon)
                
                feature = {
                    "type": "Feature",
                    "properties": {"Venue": venue_name},
                    "geometry": mapping(polygon)
                }
                features.append(feature)

            geojson_data = {"type": "FeatureCollection", "features": features}

            # Save GeoJSON file
            geojson_file = os.path.join(PROCESSED_FOLDER, "venue_polygons.geojson")
            with open(geojson_file, "w") as f:
                json.dump(geojson_data, f)

            return send_file(geojson_file, as_attachment=True, download_name="venue_polygons.geojson")

    return '''
    <!doctype html>
    <html>
    <head>
        <title>Upload CSV for GeoJSON Conversion</title>
    </head>
    <body>
        <h1>Upload CSV File</h1>
        <form action="/" method="post" enctype="multipart/form-data">
            <input type="file" name="file" required>
            <input type="submit" value="Upload and Convert">
        </form>
    </body>
    </html>
    '''

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
