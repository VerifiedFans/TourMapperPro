import os
import json
import requests
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# ✅ Load Google Maps API Key from Environment Variable
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

# ✅ Route: Serve `index.html`
@app.route("/")
def home():
    return render_template("index.html")

# ✅ Route: Get venue data and generate GeoJSON with polygons
@app.route("/get_venue_data", methods=["GET"])
def get_venue_data():
    venue_name = request.args.get("venue")
    if not venue_name:
        return jsonify({"error": "Missing venue parameter"}), 400

    try:
        # 🎯 Step 1: Get venue details
        place_url = f"https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
        params = {
            "input": venue_name,
            "inputtype": "textquery",
            "fields": "geometry,place_id,name",
            "key": GOOGLE_MAPS_API_KEY
        }
        place_response = requests.get(place_url, params=params)
        place_data = place_response.json()

        if not place_data.get("candidates"):
            return jsonify({"error": "Venue not found"}), 404

        place = place_data["candidates"][0]
        place_id = place["place_id"]
        location = place["geometry"]["location"]

        # 🎯 Step 2: Get Place Details for boundaries
        details_url = f"https://maps.googleapis.com/maps/api/place/details/json"
        details_params = {
            "place_id": place_id,
            "fields": "geometry,name,formatted_address,photos",
            "key": GOOGLE_MAPS_API_KEY
        }
        details_response = requests.get(details_url, params=details_params)
        details_data = details_response.json()

        if not details_data.get("result"):
            return jsonify({"error": "Could not fetch venue details"}), 500

        venue_info = details_data["result"]
        address = venue_info.get("formatted_address", "Unknown Address")

        # 🎯 Step 3: Get Parking & Property Boundaries
        parking_url = f"https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        parking_params = {
            "location": f"{location['lat']},{location['lng']}",
            "radius": 500,  # Search in a 500m radius
            "type": "parking",
            "key": GOOGLE_MAPS_API_KEY
        }
        parking_response = requests.get(parking_url, params=parking_params)
        parking_data = parking_response.json()

        # 🎯 Step 4: Construct GeoJSON
        geojson_data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [location["lng"], location["lat"]]
                    },
                    "properties": {
                        "name": venue_info["name"],
                        "address": address,
                        "type": "venue"
                    }
                }
            ]
        }

        # Add parking locations as polygons
        for parking in parking_data.get("results", []):
            if "geometry" in parking:
                parking_location = parking["geometry"]["location"]
                geojson_data["features"].append({
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[
                            [parking_location["lng"] - 0.0005, parking_location["lat"] - 0.0005],
                            [parking_location["lng"] + 0.0005, parking_location["lat"] - 0.0005],
                            [parking_location["lng"] + 0.0005, parking_location["lat"] + 0.0005],
                            [parking_location["lng"] - 0.0005, parking_location["lat"] + 0.0005],
                            [parking_location["lng"] - 0.0005, parking_location["lat"] - 0.0005]
                        ]]
                    },
                    "properties": {
                        "name": parking["name"],
                        "type": "parking"
                    }
                })

        # 🎯 Step 5: Save GeoJSON file
        with open("static/events.geojson", "w") as f:
            json.dump(geojson_data, f, indent=4)

        return jsonify(geojson_data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ✅ Run Flask
if __name__ == "__main__":
    app.run(debug=True)


