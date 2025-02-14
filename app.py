from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import requests
import geojson
import json
from shapely.geometry import Polygon

# Replace with your actual Google Maps API Key
GOOGLE_MAPS_API_KEY = "YOUR_GOOGLE_API_KEY"

app = FastAPI()

# Serve static files (like CSS)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Home page with the form
@app.get("/", response_class=HTMLResponse)
async def home():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>GeoJSON Generator</title>
        <script>
            async function generateGeoJSON() {
                let address = document.getElementById("address").value;
                let response = await fetch("/generate-geojson", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ address: address })
                });

                let result = await response.json();
                if (result.file) {
                    document.getElementById("download-link").style.display = "block";
                } else {
                    alert("Error: " + result.error);
                }
            }
        </script>
    </head>
    <body>
        <h1>Enter Address to Generate GeoJSON</h1>
        <input type="text" id="address" placeholder="Enter Address">
        <button onclick="generateGeoJSON()">Generate</button>
        <br><br>
        <a id="download-link" href="/download-geojson" style="display: none;">Download GeoJSON</a>
    </body>
    </html>
    """

# Function to get latitude & longitude from Google Maps API
def get_coordinates(address):
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={GOOGLE_MAPS_API_KEY}"
    response = requests.get(url).json()
    if response["status"] == "OK":
        location = response["results"][0]["geometry"]["location"]
        return location["lat"], location["lng"]
    return None

# Function to get building footprint from OpenStreetMap
def get_building_footprint(lat, lng):
    overpass_url = "http://overpass-api.de/api/interpreter"
    query = f"""
    [out:json];
    way(around:50,{lat},{lng})["building"];
    out geom;
    """
    response = requests.get(overpass_url, params={"data": query}).json()
    
    if "elements" in response and response["elements"]:
        for element in response["elements"]:
            if "geometry" in element:
                return [(p["lon"], p["lat"]) for p in element["geometry"]]
    
    return None

# Function to generate a GeoJSON file
def create_geojson(coords, output_file="building.geojson"):
    polygon = Polygon(coords)
    feature = geojson.Feature(geometry=polygon, properties={})
    feature_collection = geojson.FeatureCollection([feature])

    with open(output_file, "w") as f:
        json.dump(feature_collection, f, indent=2)

    return output_file

# API Route: Generate GeoJSON
@app.post("/generate-geojson")
async def generate_geojson_file(request: Request):
    data = await request.json()
    address = data.get("address")

    # Get coordinates
    coords = get_coordinates(address)
    if not coords:
        return JSONResponse(content={"error": "Address not found"}, status_code=400)

    # Get building footprint
    footprint = get_building_footprint(*coords)
    if not footprint:
        return JSONResponse(content={"error": "No building footprint found"}, status_code=404)

    # Create GeoJSON
    geojson_file = create_geojson(footprint)

    return JSONResponse(content={"file": geojson_file})

# API Route: Download GeoJSON
@app.get("/download-geojson")
async def download_geojson():
    return FileResponse("building.geojson", media_type="application/json", filename="building.geojson")
  
