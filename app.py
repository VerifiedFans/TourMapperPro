
import os
import json
import googlemaps
from flask import Flask, request, jsonify, render_template, send_from_directory

# Load API key from Heroku environment variable
GOOGLE_MAPS_API_KEY = os.getenv(AIzaSyDPyDGaLSn31QsLI-xXsTw0IFof8Bzn1KY)
if not GOOGLE_MAPS_API_KEY:
    raise ValueError("Missing Google Maps API key. Set it in Heroku.")

# Initialize Flask app & Google Maps client
app = Flask(__name__)
gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

# GeoJSON file location
GEOJSON_FILE = "static/events.geojson"

@app.route("/")
def home():
    """Render the index page."""
    return render_template("index.html")

@app.route("/get_venue", methods=["GET"])
def get_venue():
    """Get venue footprint and return GeoJSON response."""
    venue_name = request.args.get("name")
    if not venue_name:
        return jsonify({"error": "Venue name is required"}), 400

    geojson_data = get_venue_data(venue_name)

    if geojson_data:
        # Save to file
        save_geojson(geojson_data)
        return jsonify(geojson_data)
    
    return jsonify({"error": "Could not fetch venue data"}), 500

@app.route("/static/events.geojson")
def serve_geojson():
    """Serve the generated GeoJSON file."""
    return send_from_directory("static", "events.geojson")

def get_venue_data(venue_name):
    """Fetch venue footprint and return as GeoJSON."""
    try:
        geocode_result = gmaps.geocode(venue_name)

        if not geocode_result:
            return None  # Venue not found

        place_id = geocode_result[0]["place_id"]
        place_details = gmaps.place(place_id, fields=["geometry"])

        if "geometry" in place_details["result"] and "viewport" in place_details["result"]["geometry"]:
            bounds = place_details["result"]["geometry"]["viewport"]

            # Create a polygon for the venue footprint
            polygon = {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [bounds["southwest"]["lng"], bounds["southwest"]["lat"]],
                        [bounds["northeast"]["lng"], bounds["southwest"]["lat"]],
                        [bounds["northeast"]["lng"], bounds["northeast"]["lat"]],
                        [bounds["southwest"]["lng"], bounds["northeast"]["lat"]],
                        [bounds["southwest"]["lng"], bounds["southwest"]["lat"]]
                    ]]
                },
                "properties": {"name": venue_name}
            }
            return polygon
    except Exception as e:
        print(f"Error fetching venue: {str(e)}")
        return None

def save_geojson(geojson_data):
    """Save the GeoJSON data to a file."""
    try:
        geojson_output = {
            "type": "FeatureCollection",
            "features": [geojson_data]
        }

        with open(GEOJSON_FILE, "w") as f:
            json.dump(geojson_output, f, indent=4)
    except Exception as e:
        print(f"Error saving GeoJSON: {str(e)}")

if __name__ == "__main__":
    app.run(debug=True)
