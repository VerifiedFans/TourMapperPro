import os
import time
import json
import requests
import geopandas as gpd
from shapely.geometry import Polygon, Point
from flask import Flask, request, jsonify, render_template
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

app = Flask(__name__)

# Google Maps API Key (Ensure you have this set up in Heroku)
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")


def scrape_data(url):
    """
    Scrape venue details from the given URL using Selenium.
    This function needs to be customized based on the actual website structure.
    """
    try:
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        
        driver.get(url)
        time.sleep(2)  # Let the page load

        # Sample data extraction (Modify based on the website structure)
        name = driver.find_element("xpath", "//h1").text  
        address = driver.find_element("xpath", "//p[@class='address']").text  
        
        driver.quit()

        return {
            "name": name,
            "address": address,
            "city": "Unknown",
            "state": "Unknown",
            "zip": "00000",
            "date": time.strftime("%Y-%m-%d")
        }
    except Exception as e:
        return {"error": f"Scraping failed: {str(e)}"}


def get_parking_polygon(venue_address):
    """
    Uses Google Maps API to find nearby parking lots and create a polygon around them.
    """
    try:
        url = f"https://maps.googleapis.com/maps/api/place/textsearch/json?query=parking+near+{venue_address}&key={GOOGLE_MAPS_API_KEY}"
        response = requests.get(url)
        data = response.json()

        if "results" not in data or not data["results"]:
            return None  # No parking areas found

        # Create polygons around parking locations
        parking_coords = []
        for place in data["results"]:
            location = place["geometry"]["location"]
            lat, lng = location["lat"], location["lng"]

            # Creating a small square polygon around the parking location
            offset = 0.0001
            polygon = [
                (lng - offset, lat - offset),
                (lng - offset, lat + offset),
                (lng + offset, lat + offset),
                (lng + offset, lat - offset),
                (lng - offset, lat - offset),
            ]
            parking_coords.append(polygon)

        return parking_coords
    except Exception as e:
        return None  # Fail silently if there's an error


@app.route("/")
def home():
    """
    Render the main HTML page.
    """
    return render_template("index.html")


@app.route("/process-urls", methods=["POST"])
def process_urls():
    """
    Handle URL submissions, scrape data, generate polygons, and track progress.
    """
    data = request.get_json()

    if not data or "urls" not in data or not isinstance(data["urls"], list):
        return jsonify({"error": "Invalid input: 'urls' must be a list"}), 400

    urls = data["urls"]
    results = {"type": "FeatureCollection", "features": []}

    for i, url in enumerate(urls):
        venue_data = scrape_data(url)
        if "error" in venue_data:
            return jsonify(venue_data), 500  # Return error if scraping fails

        # Generate a sample polygon for the venue
        venue_polygon = [
            (-122.4 + i * 0.01, 37.8),
            (-122.4 + i * 0.01, 37.81),
            (-122.39 + i * 0.01, 37.81),
            (-122.39 + i * 0.01, 37.8),
            (-122.4 + i * 0.01, 37.8),
        ]

        # Get parking polygons
        parking_polygons = get_parking_polygon(venue_data["address"])

        # Add venue data
        results["features"].append({
            "type": "Feature",
            "properties": venue_data,
            "geometry": {"type": "Polygon", "coordinates": [venue_polygon]}
        })

        # Add parking areas if available
        if parking_polygons:
            for parking in parking_polygons:
                results["features"].append({
                    "type": "Feature",
                    "properties": {"name": "Parking Area"},
                    "geometry": {"type": "Polygon", "coordinates": [parking]}
                })

        # Simulate progress update
        time.sleep(1)

    return jsonify(results)


if __name__ == "__main__":
    app.run(debug=True)
