
from flask import Flask, render_template, request, jsonify, send_from_directory
import googlemaps
import os
import json

# Initialize Flask app
app = Flask(__name__)

# Load Google Maps API Key from environment variables
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
if not GOOGLE_MAPS_API_KEY:
    raise ValueError("Google Maps API Key is missing! Set GOOGLE_MAPS_API_KEY in Heroku config.")

# Initialize Google Maps Client
gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

# Serve static files (for KML and GeoJSON)
@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory("static", filename)

# **Homepage Route**
@app.route('/')
def index():
    return render_template('index.html')

# **API Route to Get Venue Data**
@app.route('/api/get_venue_data', methods=['GET'])
def get_venue_data():
    venue_name = request.args.get('venue', '')
    
    if not venue_name:
        return jsonify({"error": "Missing venue name"}), 400

    try:
        # Fetch geolocation data
        geocode_result = gmaps.geocode(venue_name)
        if not geocode_result:
            return jsonify({"error": "Venue not found"}), 404

        location = geocode_result[0]['geometry']['location']
        lat, lng = location['lat'], location['lng']

        # Fetch venue footprint (polygons)
        place_details = gmaps.place(geocode_result[0]['place_id'], fields=["geometry"])
        bounds = place_details.get("result", {}).get("geometry", {}).get("viewport", {})

        # Format response
        response = {
            "venue": venue_name,
            "lat": lat,
            "lng": lng,
            "bounds": bounds
        }

        return jsonify(response)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# **API Route to Generate GeoJSON**
@app.route('/api/generate_geojson', methods=['GET'])
def generate_geojson():
    venue_name = request.args.get('venue', '')
    if not venue_name:
        return jsonify({"error": "Missing venue name"}), 400

    try:
        # Fetch geolocation
        geocode_result = gmaps.geocode(venue_name)
        if not geocode_result:
            return jsonify({"error": "Venue not found"}), 404

        location = geocode_result[0]['geometry']['location']
        lat, lng = location['lat'], location['lng']

        # Fetch place details
        place_details = gmaps.place(geocode_result[0]['place_id'], fields=["geometry"])
        bounds = place_details.get("result", {}).get("geometry", {}).get("viewport", {})

        # Create GeoJSON
        geojson_data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [lng, lat]
                    },
                    "properties": {
                        "name": venue_name,
                        "type": "Venue Location"
                    }
                },
                {
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
                    "properties": {
                        "name": venue_name,
                        "type": "Venue Footprint"
                    }
                }
            ]
        }

        # Save GeoJSON file
        geojson_path = "static/events.geojson"
        with open(geojson_path, "w") as geojson_file:
            json.dump(geojson_data, geojson_file)

        return jsonify({"message": "GeoJSON generated successfully", "file": geojson_path})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# **Run Flask App**
if __name__ == '__main__':
    app.run(debug=True)
