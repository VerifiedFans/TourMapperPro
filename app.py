
import os
import json
import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

# Load Google Maps API Key from environment variables
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")

if not GOOGLE_MAPS_API_KEY:
    raise ValueError("Google Maps API Key is missing! Set it using Heroku config.")

def get_place_details(place_name):
    """Fetches place details including place_id from Google Places API."""
    url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
    params = {
        "input": place_name,
        "inputtype": "textquery",
        "fields": "geometry,formatted_address,name,place_id",
        "key": GOOGLE_MAPS_API_KEY
    }
    response = requests.get(url, params=params)
    return response.json()

def get_place_polygon(place_id):
    """Fetches detailed venue geometry (building footprint) from Google Places API."""
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "fields": "geometry",
        "key": GOOGLE_MAPS_API_KEY
    }
    response = requests.get(url, params=params)
    return response.json()

def get_parking_nearby(lat, lng, radius=500):
    """Finds nearby parking areas using Google Places API."""
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {
        "location": f"{lat},{lng}",
        "radius": radius,  # Search radius in meters
        "type": "parking",
        "key": GOOGLE_MAPS_API_KEY
    }
    response = requests.get(url, params=params)
    return response.json()

@app.route("/venue/<venue_name>", methods=["GET"])
def venue_info(venue_name):
    """Returns venue details including polygons for mapping."""
    place_data = get_place_details(venue_name)
    
    if not place_data.get("candidates"):
        return jsonify({"error": "Venue not found"}), 404

    place = place_data["candidates"][0]
    place_id = place["place_id"]
    venue_geometry = get_place_polygon(place_id)

    if "geometry" not in venue_geometry.get("result", {}):
        return jsonify({"error": "Geometry not available"}), 404

    venue_location = venue_geometry["result"]["geometry"]["location"]
    lat, lng = venue_location["lat"], venue_location["lng"]

    # Get nearby parking areas
    parking_data = get_parking_nearby(lat, lng)
    parking_features = []

    if "results" in parking_data:
        for park in parking_data["results"]:
            park_geometry = park.get("geometry", {}).get("location", {})
            if park_geometry:
                parking_features.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [park_geometry["lng"], park_geometry["lat"]]
                    },
                    "properties": {
                        "name": park.get("name", "Unknown Parking"),
                        "address": park.get("vicinity", "Unknown Address"),
                        "rating": park.get("rating", "N/A")
                    }
                })

    # Create GeoJSON response
    geojson_response = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [lng, lat]
                },
                "properties": {
                    "name": place["name"],
                    "address": place["formatted_address"]
                }
            }
        ] + parking_features
    }

    # Save GeoJSON to file
    geojson_path = os.path.join("static", "events.geojson")
    with open(geojson_path, "w") as geojson_file:
        json.dump(geojson_response, geojson_file, indent=4)

    return jsonify({"message": "Venue and parking data saved", "geojson": geojson_response})

@app.route("/")
def home():
    return jsonify({"message": "Welcome to TourMapper API!"})

if __name__ == "__main__":
    app.run(debug=True)


