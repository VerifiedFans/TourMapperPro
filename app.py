import os
import json
import redis
import requests
from flask import Flask, request, jsonify

# Initialize Flask App
app = Flask(__name__)

# Load environment variables
REDIS_URL = os.getenv("REDIS_URL")
GMAPS_API_KEY = os.getenv("GMAPS_API_KEY")

# Ensure required environment variables are set
if not REDIS_URL:
    raise ValueError("ERROR: REDIS_URL is not set. Check your Heroku config vars.")

if not GMAPS_API_KEY:
    raise ValueError("ERROR: GMAPS_API_KEY is not set. Check your Heroku config vars.")

# Initialize Redis client
try:
    redis_client = redis.StrictRedis.from_url(REDIS_URL, decode_responses=True, ssl=True)
except Exception as e:
    raise ValueError(f"Failed to connect to Redis: {str(e)}")


### 1️⃣ Route: Home Page
@app.route("/")
def home():
    return jsonify({"message": "Welcome to TourMapperPro API!"})


### 2️⃣ Route: Get Lat/Lon from Address using Google Maps API
@app.route("/get-coordinates", methods=["POST"])
def get_coordinates():
    data = request.json
    address = data.get("address")

    if not address:
        return jsonify({"error": "Missing address"}), 400

    try:
        # Call Google Maps Geocoding API
        response = requests.get(
            f"https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={GMAPS_API_KEY}"
        )
        geocode_data = response.json()

        if geocode_data["status"] != "OK":
            return jsonify({"error": "Failed to retrieve coordinates"}), 500

        location = geocode_data["results"][0]["geometry"]["location"]
        lat, lon = location["lat"], location["lng"]

        return jsonify({"address": address, "latitude": lat, "longitude": lon})

    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500


### 3️⃣ Route: Store & Retrieve Data from Redis
@app.route("/store-data", methods=["POST"])
def store_data():
    data = request.json
    key = data.get("key")
    value = data.get("value")

    if not key or not value:
        return jsonify({"error": "Missing key or value"}), 400

    redis_client.set(key, json.dumps(value))
    return jsonify({"message": "Data stored successfully"})


@app.route("/get-data/<key>", methods=["GET"])
def get_data(key):
    value = redis_client.get(key)
    
    if not value:
        return jsonify({"error": "Data not found"}), 404

    return jsonify({"key": key, "value": json.loads(value)})


### 4️⃣ Route: Draw Building Footprint Polygons (GeoJSON Format)
@app.route("/get-building-footprint", methods=["POST"])
def get_building_footprint():
    data = request.json
    address = data.get("address")

    if not address:
        return jsonify({"error": "Missing address"}), 400

    try:
        # Call Google Maps API for building footprints (imaginary API for now)
        # In a real-world case, use a third-party GIS provider like OpenStreetMap Overpass API
        geojson_data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [-73.985130, 40.748817],  # Example coordinates for a footprint
                                [-73.985000, 40.748700],
                                [-73.984800, 40.748900],
                                [-73.985130, 40.748817]
                            ]
                        ]
                    },
                    "properties": {"name": "Example Building"}
                }
            ]
        }

        return jsonify(geojson_data)

    except Exception as e:
        return jsonify({"error": f"Failed to retrieve building footprint: {str(e)}"}), 500


# Run Flask App (Locally)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
