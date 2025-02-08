
import os
import json
import csv
import redis
import requests
import geojson
import pandas as pd
import geopandas as gpd
from shapely.geometry import Polygon
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from flask_dropzone import Dropzone
from celery import Celery

# Initialize Flask App
app = Flask(__name__)
CORS(app)

# Load environment variables
app.config['CELERY_BROKER_URL'] = os.getenv("CELERY_BROKER_URL")
app.config['CELERY_RESULT_BACKEND'] = os.getenv("CELERY_RESULT_BACKEND")
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL", "sqlite:///data.db")

REDIS_URL = os.getenv("REDIS_URL")
GMAPS_API_KEY = os.getenv("GMAPS_API_KEY") or os.getenv("GOOGLE_MAPS_API_KEY")

# Validate API Keys
if not REDIS_URL or not GMAPS_API_KEY:
    raise ValueError("ERROR: REDIS_URL or GMAPS_API_KEY is missing. Set them in environment variables.")

# Connect to Redis
redis_client = redis.StrictRedis.from_url(REDIS_URL, decode_responses=True, ssl=True)

# Initialize Celery
celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)

db = SQLAlchemy(app)
dropzone = Dropzone(app)

# Get Coordinates from Address (Google Maps API)
@app.route("/get-coordinates", methods=["POST"])
def get_coordinates():
    data = request.json
    address = data.get("address")
    if not address:
        return jsonify({"error": "Missing address"}), 400

    response = requests.get(
        f"https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={GMAPS_API_KEY}"
    )
    geocode_data = response.json()

    if geocode_data["status"] != "OK":
        return jsonify({"error": "Failed to retrieve coordinates"}), 500

    location = geocode_data["results"][0]["geometry"]["location"]
    lat, lon = location["lat"], location["lng"]
    return jsonify({"address": address, "latitude": lat, "longitude": lon})

# Generate a GeoJSON Polygon for the Venue
@app.route("/generate-geojson", methods=["POST"])
def generate_geojson():
    data = request.json
    coordinates = data.get("coordinates")  # List of [lat, lon] points

    if not coordinates or len(coordinates) < 3:
        return jsonify({"error": "Invalid polygon coordinates"}), 400

    polygon = Polygon(coordinates)
    geojson_data = geojson.Feature(geometry=polygon, properties={"type": "Venue Boundary"})
    
    # Save GeoJSON to file
    with open("venue_polygon.geojson", "w") as geojson_file:
        geojson.dump(geojson_data, geojson_file)

    return jsonify({"message": "GeoJSON file created", "file": "venue_polygon.geojson"})

# Export Data to CSV
@app.route("/download-csv", methods=["GET"])
def download_csv():
    csv_file = "venue_data.csv"
    
    data = [
        {"Venue": "Test Venue", "Latitude": 40.7128, "Longitude": -74.0060},
        # Additional data rows
    ]
    
    df = pd.DataFrame(data)
    df.to_csv(csv_file, index=False)
    return send_file(csv_file, as_attachment=True)

# Home Route
@app.route("/")
def home():
    return jsonify({"message": "Welcome to TourMapperPro API!"})

# Run Flask App
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
