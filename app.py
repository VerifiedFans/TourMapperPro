from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import json
import requests

app = Flask(__name__)

# Store URLs and scraped data
uploaded_urls = []
scraped_data = []

# Google Places API Setup
GOOGLE_PLACES_API_KEY = "YOUR_GOOGLE_PLACES_API_KEY"

# Ensure static folder exists for storing geojson/kml files
if not os.path.exists("static"):
    os.makedirs("static")

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/upload_urls", methods=["POST"])
def upload_urls():
    global uploaded_urls
    data = request.json
    uploaded_urls = data.get("urls", [])
    return jsonify({"message": "URLs uploaded successfully", "uploaded_urls": uploaded_urls})

@app.route("/view_urls")
def view_urls():
    return render_template("view_urls.html", urls=uploaded_urls)

@app.route("/clear_urls", methods=["POST"])
def clear_urls():
    global uploaded_urls
    uploaded_urls = []
    return jsonify({"message": "URLs cleared successfully"})

@app.route("/start_scraping", methods=["POST"])
def start_scraping():
    global scraped_data
    scraped_data = []

    if not uploaded_urls:
        return jsonify({"error": "No URLs uploaded"}), 400

    for url in uploaded_urls:
        # Simulate scraping by using Google Places API
        place_name = url  # Assume URL contains place name for simplicity
        api_url = f"https://maps.googleapis.com/maps/api/place/findplacefromtext/json?input={place_name}&inputtype=textquery&fields=geometry,formatted_address,name,rating&key={GOOGLE_PLACES_API_KEY}"
        
        response = requests.get(api_url)
        data = response.json()

        if "candidates" in data and len(data["candidates"]) > 0:
            place = data["candidates"][0]
            scraped_data.append({
                "name": place.get("name"),
                "address": place.get("formatted_address"),
                "rating": place.get("rating"),
                "geometry": place.get("geometry", {}).get("location", {})
            })

    # Save GeoJSON and KML
    save_geojson()
    save_kml()

    return jsonify({"message": "Scraping completed", "scraped_data": scraped_data})

def save_geojson():
    geojson_data = {
        "type": "FeatureCollection",
        "features": []
    }

    for place in scraped_data:
        if "geometry" in place:
            geojson_data["features"].append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [place["geometry"]["lng"], place["geometry"]["lat"]]
                },
                "properties": {
                    "name": place["name"],
                    "address": place["address"],
                    "rating": place["rating"]
                }
            })

    with open("static/events.geojson", "w") as f:
        json.dump(geojson_data, f)

def save_kml():
    kml_data = """<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
    <Document>"""

    for place in scraped_data:
        if "geometry" in place:
            kml_data += f"""
            <Placemark>
                <name>{place["name"]}</name>
                <description>{place["address"]} (Rating: {place["rating"]})</description>
                <Point>
                    <coordinates>{place["geometry"]["lng"]},{place["geometry"]["lat"]},0</coordinates>
                </Point>
            </Placemark>"""

    kml_data += "</Document></kml>"

    with open("static/events.kml", "w") as f:
        f.write(kml_data)

@app.route("/static/<path:filename>")
def serve_static(filename):
    return send_from_directory("static", filename)

if __name__ == "__main__":
    app.run(debug=True)
