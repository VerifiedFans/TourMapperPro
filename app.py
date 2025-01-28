import os
import json
import time
from flask import Flask, render_template, request, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import simplekml
from googlemaps import Client as GoogleMapsClient

app = Flask(__name__)

# Google Maps API client
gmaps = GoogleMapsClient(key=os.getenv("GOOGLE_MAPS_API_KEY"))

# List to hold URLs dynamically
url_storage = []

@app.route("/")
def index():
    """Render the home page."""
    return render_template("index.html")

@app.route("/upload-urls", methods=["POST"])
def upload_urls():
    """Receive and store URLs."""
    data = request.get_json()
    urls = data.get("urls", [])
    if not urls:
        return jsonify({"status": "error", "message": "No URLs provided."})
    url_storage.extend(urls)
    return jsonify({"status": "success", "message": f"{len(urls)} URLs uploaded successfully."})

@app.route("/process", methods=["POST"])
def process_urls():
    """Process the stored URLs."""
    if not url_storage:
        return jsonify({"status": "error", "message": "No URLs to process."})

    all_event_data = []

    # Configure Selenium WebDriver
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    driver_path = os.getenv("CHROMEDRIVER_PATH", "/app/.chromedriver/bin/chromedriver")

    for url in url_storage:
        try:
            browser = webdriver.Chrome(driver_path, options=chrome_options)
            browser.get(url)

            # Locate and scrape event data
            events = []
            while True:
                time.sleep(2)  # Allow page to load
                event_elements = browser.find_elements(By.CSS_SELECTOR, ".event")
                for event in event_elements:
                    try:
                        date = event.find_element(By.CSS_SELECTOR, ".event-date").text
                        venue = event.find_element(By.CSS_SELECTOR, ".event-venue").text
                        location = event.find_element(By.CSS_SELECTOR, ".event-location").text

                        # Geocode location using Google Maps API
                        geocode_result = gmaps.geocode(location)
                        if geocode_result:
                            lat = geocode_result[0]["geometry"]["location"]["lat"]
                            lng = geocode_result[0]["geometry"]["location"]["lng"]
                        else:
                            lat, lng = None, None

                        events.append({"date": date, "venue": venue, "location": location, "lat": lat, "lng": lng})
                    except Exception as e:
                        print(f"Error extracting event data: {e}")

                # Check for pagination
                show_more_button = browser.find_elements(By.LINK_TEXT, "Show More Dates")
                if show_more_button:
                    show_more_button[0].click()
                    time.sleep(2)
                else:
                    break

            all_event_data.extend(events)
            browser.quit()

        except Exception as e:
            print(f"Error processing URL {url}: {e}")

    if not all_event_data:
        return jsonify({"status": "success", "message": "No events found."})

    # Generate KML and GeoJSON
    kml = simplekml.Kml()
    geojson = {"type": "FeatureCollection", "features": []}
    for event in all_event_data:
        if event["lat"] and event["lng"]:
            kml.newpoint(name=event["venue"], description=event["date"], coords=[(event["lng"], event["lat"])])
            geojson["features"].append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [event["lng"], event["lat"]]},
                "properties": {"date": event["date"], "venue": event["venue"], "location": event["location"]},
            })

    kml_file = "events.kml"
    geojson_file = "events.geojson"
    kml.save(kml_file)
    with open(geojson_file, "w") as geojson_fp:
        json.dump(geojson, geojson_fp)

    return jsonify({"status": "success", "message": "Processing complete. Files generated.", "data": all_event_data})

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
