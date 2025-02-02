import os
import json
import requests
from flask import Flask, render_template, request, jsonify, send_from_directory

app = Flask(__name__)

# Get API Key from Heroku Config
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")


### 🔹 1. Home Route
@app.route('/')
def home():
    return render_template('index.html')


### 🔹 2. Fetch Venue Footprint & Parking Area
def get_venue_polygon(venue_name):
    """Fetch venue footprint and parking area as polygons."""
    
    # Step 1: Get Place ID
    find_place_url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
    params = {
        "input": venue_name,
        "inputtype": "textquery",
        "fields": "place_id,name,formatted_address,geometry",
        "key": GOOGLE_MAPS_API_KEY
    }
    response = requests.get(find_place_url, params=params)
    data = response.json()

    if not data.get("candidates"):
        return None

    place_id = data["candidates"][0]["place_id"]

    # Step 2: Get Detailed Data
    details_url = "https://maps.googleapis.com/maps/api/place/details/json"
    details_params = {
        "place_id": place_id,
        "fields": "name,geometry,formatted_address",
        "key": GOOGLE_MAPS_API_KEY
    }
    details_response = requests.get(details_url, params=details_params)
    details_data = details_response.json()

    if "result" not in details_data:
        return None

    result = details_data["result"]
    
    # Step 3: Construct GeoJSON Polygon
    geometry = result["geometry"]["location"]
    venue_polygon = {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [geometry["lng"] - 0.001, geometry["lat"] - 0.001],  # Bottom left
                [geometry["lng"] + 0.001, geometry["lat"] - 0.001],  # Bottom right
                [geometry["lng"] + 0.001, geometry["lat"] + 0.001],  # Top right
                [geometry["lng"] - 0.001, geometry["lat"] + 0.001],  # Top left
                [geometry["lng"] - 0.001, geometry["lat"] - 0.001]   # Close polygon
            ]]
        },
        "properties": {
            "name": result["name"],
            "address": result["formatted_address"],
            "type": "Venue"
        }
    }

    # Step 4: Add Parking (Mocking It Here, but Can Use Google Maps API)
    parking_polygon = {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [geometry["lng"] - 0.0015, geometry["lat"] - 0.0015],
                [geometry["lng"] + 0.0015, geometry["lat"] - 0.0015],
                [geometry["lng"] + 0.0015, geometry["lat"] + 0.0015],
                [geometry["lng"] - 0.0015, geometry["lat"] + 0.0015],
                [geometry["lng"] - 0.0015, geometry["lat"] - 0.0015]
            ]]
        },
        "properties": {
            "name": f"{result['name']} Parking",
            "type": "Parking"
        }
    }

    return [venue_polygon, parking_polygon]


### 🔹 3. Scrape & Generate GeoJSON
@app.route('/start_scraping', methods=['POST'])
def start_scraping():
    venues = ["Madison Square Garden", "Times Square", "Yankee Stadium"]  # Example venues
    features = []

    for venue in venues:
        venue_polygons = get_venue_polygon(venue)
        if venue_polygons:
            features.extend(venue_polygons)

    geojson_data = {
        "type": "FeatureCollection",
        "features": features
    }

    # Save as GeoJSON
    with open("static/events.geojson", "w") as geojson_file:
        json.dump(geojson_data, geojson_file)

    return jsonify({"message": "Scraping complete!", "geojson_file": "static/events.geojson"})


### 🔹 4. Serve GeoJSON File
@app.route('/static/<filename>')
def serve_file(filename):
    return send_from_directory("static", filename)


### 🔹 5. Run Flask App
if __name__ == '__main__':
    app.run(debug=True)
