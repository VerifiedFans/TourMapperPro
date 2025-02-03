import os
from flask import Flask, render_template, request, send_from_directory, jsonify
import googlemaps

app = Flask(__name__)

# Load the Google Maps API key from Heroku environment variables
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

if not GOOGLE_MAPS_API_KEY:
    raise ValueError("Missing Google Maps API key. Set it in Heroku.")

# Initialize Google Maps client
gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)


@app.route("/")
def index():
    """Render the homepage and pass the Google Maps API key."""
    return render_template("index.html", google_maps_api_key=GOOGLE_MAPS_API_KEY)


@app.route("/static/<path:filename>")
def static_files(filename):
    """Serve static files like GeoJSON and KML."""
    return send_from_directory("static", filename)


@app.route("/get-events")
def get_events():
    """API endpoint to return event data in GeoJSON format."""
    geojson_data = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [-74.0060, 40.7128]  # Example: NYC coordinates
                },
                "properties": {
                    "name": "Madison Square Garden Event",
                    "description": "A sample event happening at MSG"
                }
            }
        ]
    }
    return jsonify(geojson_data)


@app.route("/get-coordinates", methods=["GET"])
def get_coordinates():
    """Fetch coordinates for a given address using Google Maps API."""
    address = request.args.get("address")
    if not address:
        return jsonify({"error": "No address provided"}), 400

    try:
        geocode_result = gmaps.geocode(address)
        if geocode_result:
            location = geocode_result[0]["geometry"]["location"]
            return jsonify({"lat": location["lat"], "lng": location["lng"]})
        else:
            return jsonify({"error": "Address not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)
