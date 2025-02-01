import os
import json
import requests
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__)
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "your_api_key")

uploaded_urls = []

# Upload URLs
@app.route("/upload_urls", methods=["POST"])
def upload_urls():
    global uploaded_urls
    data = request.json
    urls = data.get("urls", [])
    if not urls:
        return jsonify({"error": "No URLs provided"}), 400
    uploaded_urls = urls
    return jsonify({"message": "URLs uploaded successfully", "urls": urls})

# Scrape Data and Fetch Venue Footprints + Nearby Parking
@app.route("/start_scraping", methods=["POST"])
def start_scraping():
    if not uploaded_urls:
        return jsonify({"error": "No URLs uploaded"}), 400

    geojson_data = {
        "type": "FeatureCollection",
        "features": []
    }

    for url in uploaded_urls:
        coordinates = extract_coordinates_from_url(url)
        if coordinates:
            venue_polygon = get_venue_footprint(coordinates)
            parking_spots = get_nearby_parking(coordinates)
            if venue_polygon:
                geojson_data["features"].append(venue_polygon)
            geojson_data["features"].extend(parking_spots)

    with open("static/events.geojson", "w") as geojson_file:
        json.dump(geojson_data, geojson_file)

    return jsonify({"message": "Scraping completed, GeoJSON saved"}), 200

# Extract Coordinates from URL
def extract_coordinates_from_url(url):
    """Extracts latitude and longitude from a Google Maps URL."""
    if "@" in url:
        parts = url.split("@")[1].split(",")
        try:
            lat, lon = float(parts[0]), float(parts[1])
            return lat, lon
        except ValueError:
            return None
    return None

# Get Venue Footprint (Polygon)
def get_venue_footprint(coordinates):
    lat, lon = coordinates
    places_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {
        "location": f"{lat},{lon}",
        "radius": 50,  # Small radius to focus on venue
        "type": "point_of_interest",
        "key": GOOGLE_MAPS_API_KEY
    }

    response = requests.get(places_url, params=params)
    data = response.json()

    if "results" in data and data["results"]:
        place_id = data["results"][0]["place_id"]
        details_url = "https://maps.googleapis.com/maps/api/place/details/json"
        details_params = {
            "place_id": place_id,
            "fields": "geometry",
            "key": GOOGLE_MAPS_API_KEY
        }

        details_response = requests.get(details_url, params=details_params)
        details_data = details_response.json()

        if "result" in details_data and "geometry" in details_data["result"]:
            geometry = details_data["result"]["geometry"]
            if "viewport" in geometry:
                northeast = geometry["viewport"]["northeast"]
                southwest = geometry["viewport"]["southwest"]
                polygon = {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[
                            [northeast["lng"], northeast["lat"]],
                            [southwest["lng"], northeast["lat"]],
                            [southwest["lng"], southwest["lat"]],
                            [northeast["lng"], southwest["lat"]],
                            [northeast["lng"], northeast["lat"]]
                        ]]
                    },
                    "properties": {
                        "name": data["results"][0]["name"],
                        "address": data["results"][0]["vicinity"]
                    }
                }
                return polygon
    return None

# Get Nearby Parking
def get_nearby_parking(coordinates):
    lat, lon = coordinates
    places_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {
        "location": f"{lat},{lon}",
        "radius": 1000,  # Search within 1km
        "type": "parking",
        "key": GOOGLE_MAPS_API_KEY
    }

    response = requests.get(places_url, params=params)
    data = response.json()

    features = []
    if "results" in data:
        for place in data["results"]:
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [
                        place["geometry"]["location"]["lng"],
                        place["geometry"]["location"]["lat"]
                    ]
                },
                "properties": {
                    "name": place["name"],
                    "address": place.get("vicinity", "Unknown"),
                    "rating": place.get("rating", "N/A")
                }
            }
            features.append(feature)

    return features

# Serve static files
@app.route("/static/<path:filename>")
def serve_static(filename):
    return send_from_directory("static", filename)

if __name__ == "__main__":
    app.run(debug=True)
