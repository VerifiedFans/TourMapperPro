import os
import time
import json
import yagmail
import googlemaps
import simplekml
import threading
from flask import Flask, render_template, request, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

app = Flask(__name__)

# Load Google Maps API Key
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

# Configure the Selenium WebDriver for headless scraping
def configure_browser():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    driver_path = os.getenv("CHROMEDRIVER_PATH", "/app/.chromedriver/bin/chromedriver")
    return webdriver.Chrome(driver_path, options=chrome_options)

# Function to scrape data from a venue URL
def scrape_venue_data(url):
    browser = configure_browser()
    browser.get(url)

    try:
        # Extract event details
        venue_name = browser.find_element(By.CSS_SELECTOR, ".venue-name").text
        event_date = browser.find_element(By.CSS_SELECTOR, ".event-date").text
        address = browser.find_element(By.CSS_SELECTOR, ".event-location").text

        browser.quit()
        return {"venue": venue_name, "date": event_date, "address": address, "url": url}
    
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        browser.quit()
        return None

# Function to geocode addresses
def geocode_address(address):
    gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)
    try:
        geocode_result = gmaps.geocode(address)
        if geocode_result:
            location = geocode_result[0]["geometry"]["location"]
            return (location["lng"], location["lat"])
    except Exception as e:
        print(f"Geocoding failed for {address}: {e}")
    return (0, 0)  # Default location if geocoding fails

# Function to create and save KML & GeoJSON files
def generate_kml_geojson(events):
    kml = simplekml.Kml()
    geojson_data = {"type": "FeatureCollection", "features": []}

    for event in events:
        coords = geocode_address(event["address"])
        kml.newpoint(name=event["venue"], description=event["date"], coords=[coords])

        geojson_data["features"].append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": list(coords)},
            "properties": {"venue": event["venue"], "date": event["date"], "address": event["address"]}
        })

    kml_file = "events.kml"
    geojson_file = "events.geojson"
    
    kml.save(kml_file)
    with open(geojson_file, "w") as f:
        json.dump(geojson_data, f, indent=4)

    return kml_file, geojson_file

# Function to send email with the files
def send_email(kml_file, geojson_file):
    yag = yagmail.SMTP(os.getenv("EMAIL_USER"), os.getenv("EMAIL_PASS"))
    yag.send(
        to="troyburnsfamily@gmail.com",
        subject="Scraped Event Data",
        contents="Attached are the KML and GeoJSON files with venue data.",
        attachments=[kml_file, geojson_file]
    )

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload_urls():
    """Handles file upload and processes URLs asynchronously."""
    try:
        urls = request.form.get("urls").splitlines()
        if not urls:
            return jsonify({"status": "error", "message": "No URLs provided."}), 400
        
        events = []
        threads = []
        
        # Run scraping in parallel
        def scrape_and_store(url):
            event = scrape_venue_data(url)
            if event:
                events.append(event)

        for url in urls:
            thread = threading.Thread(target=scrape_and_store, args=(url,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        if not events:
            return jsonify({"status": "error", "message": "No valid event data found."}), 500

        # Generate KML & GeoJSON
        kml_file, geojson_file = generate_kml_geojson(events)

        # Send email with attachments
        send_email(kml_file, geojson_file)

        return jsonify({"status": "success", "message": "Processing complete. Data sent via email."})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
