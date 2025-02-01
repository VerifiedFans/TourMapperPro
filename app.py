import os
import json
import googlemaps
import requests
from flask import Flask, request, jsonify, render_template, send_from_directory

app = Flask(__name__)

# Load API key from environment variable (Make sure to set this in Heroku)
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

# Initialize Google Maps Client
gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

# Store uploaded venues (Temporary storage - use a DB for production)
venues = []


@app.route("/")
def home():
    return render_template("index.html")


# 📌 1. Get Venue Details Using Google Places API
@app.route("/get_venue", methods=["POST"])
def get_venue():
    data = request.json
    venue_name = data.get("venue_name")
    
    if not venue_name:
        return jsonify({"error": "No venue name provided"}), 400

    try:
        # Search for the venue in Google Places API
        places_result = gmaps.places(query=venue_name)
        if not places_result["results"]:
            return jsonify({"error": "Venue not found"}), 404

        place = places_result["results"][0]
        place_id = place["place_id"]
        place_details = gmaps.place(place_id=place_id, fields=["geometry", "name"])
        
        location = place_details["result"]["geometry"]["location"]
        lat, lon = location["lat"], location["lng"]
        
        venue_info = {
            "name": place["name"],
            "lat": lat,
            "lon": lon
        }
        
        # Store in venues list
        venues.append(venue_info)
        
        return jsonify(venue_info)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 📌 2. Generate GeoJSON Polygon from Venue
@app.route("/generate_geojson", methods=["GET"])
def generate_geojson():
    if not venues:
        return jsonify({"error": "No venues stored"}), 404
    
    geojson = {
        "type": "FeatureCollection",
        "features": []
    }

    for venue in venues:
        lat, lon = venue["lat"], venue["lon"]
        geojson["features"].append({
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [lon + 0.001, lat + 0.001],  # Top-right
                    [lon - 0.001, lat + 0.001],  # Top-left
                    [lon - 0.001, lat - 0.001],  # Bottom-left
                    [lon + 0.001, lat - 0.001],  # Bottom-right
                    [lon + 0.001, lat + 0.001]   # Closing point
                ]]
            },
            "properties": {
                "name": venue["name"]
            }
        })

    # Save GeoJSON file
    static_dir = os.path.join(app.root_path, "static")
    geojson_path = os.path.join(static_dir, "events.geojson")

    with open(geojson_path, "w") as f:
        json.dump(geojson, f)

    return jsonify({"message": "GeoJSON generated", "file": "/static/events.geojson"})


# 📌 3. Generate KML Polygon from Venue
@app.route("/generate_kml", methods=["GET"])
def generate_kml():
    if not venues:
        return jsonify({"error": "No venues stored"}), 404
    
    kml_content = """<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
    <Document>"""

    for venue in venues:
        lat, lon = venue["lat"], venue["lon"]
        kml_content += f"""
        <Placemark>
            <name>{venue['name']}</name>
            <Polygon>
                <outerBoundaryIs>
                    <LinearRing>
                        <coordinates>
                            {lon + 0.001},{lat + 0.001},0
                            {lon - 0.001},{lat + 0.001},0
                            {lon - 0.001},{lat - 0.001},0
                            {lon + 0.001},{lat - 0.001},0
                            {lon + 0.001},{lat + 0.001},0
                        </coordinates>
                    </LinearRing>
                </outerBoundaryIs>
            </Polygon>
        </Placemark>"""

    kml_content += "</Document></kml>"

    # Save KML file
    static_dir = os.path.join(app.root_path, "static")
    kml_path = os.path.join(static_dir, "events.kml")

    with open(kml_path, "w") as f:
        f.write(kml_content)

    return jsonify({"message": "KML generated", "file": "/static/events.kml"})


# 📌 4. Serve Static Files (GeoJSON & KML)
@app.route("/static/<path:filename>")
def serve_static(filename):
    static_dir = os.path.join(app.root_path, "static")
    return send_from_directory(static_dir, filename)


# 📌 5. View Stored Venues
@app.route("/view_urls")
def view_urls():
    return render_template("view_urls.html", venues=venues)


if __name__ == "__main__":
    app.run(debug=True)
