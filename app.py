import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
import googlemaps
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS

# Load Google Maps API Key from environment variable
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

# Initialize Geopy geocoder
geolocator = Nominatim(user_agent="geojson_app")

@app.route("/")
def home():
    return jsonify({"message": "Welcome to the GeoJSON API"}), 200

@app.route("/geocode", methods=["POST"])
def geocode():
    """
    Geocodes an address using Google Maps API.
    """
    try:
        data = request.get_json()
        address = data.get("address")

        if not address:
            return jsonify({"error": "No address provided"}), 400

        result = gmaps.geocode(address)
        if not result:
            return jsonify({"error": "Address not found"}), 404

        location = result[0]["geometry"]["location"]
        return jsonify({
            "address": result[0]["formatted_address"],
            "latitude": location["lat"],
            "longitude": location["lng"]
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/reverse-geocode", methods=["POST"])
def reverse_geocode():
    """
    Reverse geocodes a lat/lon using geopy.
    """
    try:
        data = request.get_json()
        lat = data.get("latitude")
        lon = data.get("longitude")

        if not lat or not lon:
            return jsonify({"error": "Latitude and longitude required"}), 400

        try:
            location = geolocator.reverse((lat, lon), exactly_one=True)
            if location is None:
                return jsonify({"error": "Location not found"}), 404

            return jsonify({"address": location.address}), 200

        except GeocoderTimedOut:
            return jsonify({"error": "Geocoding service timed out"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/generate-geojson", methods=["POST"])
def generate_geojson():
    """
    Converts an address into GeoJSON format.
    """
    try:
        data = request.get_json()
        address = data.get("address")

        if not address:
            return jsonify({"error": "No address provided"}), 400

        result = gmaps.geocode(address)
        if not result:
            return jsonify({"error": "Address not found"}), 404

        location = result[0]["geometry"]["location"]

        geojson = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [location["lng"], location["lat"]]
            },
            "properties": {
                "address": result[0]["formatted_address"]
            }
        }

        return jsonify(geojson), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
  
