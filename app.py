import os
import time
import json
import logging
from flask import Flask, render_template, request, send_file, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
import yagmail
import simplekml
import googlemaps
import io

# Setup logging
logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

# Load Google API Key from Heroku
GOOGLE_API_KEY = os.getenv('GMAPS_API_KEY')
EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASS = os.getenv('EMAIL_PASS')

if not GOOGLE_API_KEY:
    logging.error("❌ Google Maps API key is missing!")
if not EMAIL_USER or not EMAIL_PASS:
    logging.error("❌ Email credentials are missing!")

# Store URLs permanently
URL_FILE = "urls.txt"

@app.route('/')
def index():
    """Render the home page."""
    return render_template('index.html')

@app.route('/upload_urls', methods=['POST'])
def upload_urls():
    """Save uploaded URLs to a file."""
    try:
        data = request.json
        urls = data.get('urls', [])
        
        if not urls:
            return jsonify({"status": "error", "message": "No URLs provided"}), 400

        with open(URL_FILE, 'a') as f:
            for url in urls:
                f.write(url + '\n')

        return jsonify({"status": "success", "message": "URLs uploaded successfully!"})
    
    except Exception as e:
        logging.error(f"Error saving URLs: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/view_urls', methods=['GET'])
def view_urls():
    """View uploaded URLs."""
    try:
        if not os.path.exists(URL_FILE):
            return jsonify({"urls": []})
        
        with open(URL_FILE, 'r') as f:
            urls = f.read().splitlines()

        return jsonify({"urls": urls})

    except Exception as e:
        logging.error(f"Error reading URLs: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/start_scraping', methods=['POST'])
def start_scraping():
    """Scrape events and generate KML/GeoJSON."""
    try:
        if not os.path.exists(URL_FILE):
            return jsonify({"status": "error", "message": "No URLs found"}), 400
        
        with open(URL_FILE, 'r') as f:
            urls = f.read().splitlines()

        if not urls:
            return jsonify({"status": "error", "message": "No URLs to scrape"}), 400

        # Configure Chrome WebDriver
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')

        driver_path = "/app/.chromedriver/bin/chromedriver"
        service = Service(driver_path)
        browser = webdriver.Chrome(service=service, options=chrome_options)

        events = []
        
        for artist_url in urls:
            logging.info(f"Scraping: {artist_url}")
            browser.get(artist_url)

            # Locate and click "Past" link
            try:
                past_button = WebDriverWait(browser, 10).until(
                    EC.element_to_be_clickable((By.LINK_TEXT, "Past"))
                )
                past_button.click()
                time.sleep(2)
            except Exception as e:
                logging.warning(f"❌ No 'Past' button found for {artist_url}: {e}")
                continue

            event_elements = browser.find_elements(By.CSS_SELECTOR, '.event')

            for event in event_elements:
                try:
                    event_data = {
                        "date": event.find_element(By.CSS_SELECTOR, '.EfW1v6YNlQnbyB7fUHmR').text,  # Date
                        "venue": event.find_element(By.CSS_SELECTOR, '.q1Vlsw1cdclAUZ4gBvAn').text,  # Venue
                        "address": event.find_element(By.CSS_SELECTOR, 'div').text,  # Address
                        "city_state_zip": event.find_element(By.CSS_SELECTOR, 'a[href*="bandsintown.com/c"]').text  # City, State, Zip
                    }
                    events.append(event_data)
                except Exception as e:
                    logging.error(f"❌ Error extracting event data: {e}")

        browser.quit()

        if not events:
            return jsonify({"status": "error", "message": "No valid events found!"})

        # Geocode & Generate KML/GeoJSON
        gmaps = googlemaps.Client(key=GOOGLE_API_KEY)
        kml = simplekml.Kml()
        geojson_data = {"type": "FeatureCollection", "features": []}

        for event in events:
            try:
                location = f"{event['address']}, {event['city_state_zip']}"
                geocode_result = gmaps.geocode(location)

                if geocode_result:
                    lat = geocode_result[0]["geometry"]["location"]["lat"]
                    lng = geocode_result[0]["geometry"]["location"]["lng"]
                    event["latitude"] = lat
                    event["longitude"] = lng
                else:
                    lat, lng = 0, 0

                kml.newpoint(name=event["venue"], description=event["date"], coords=[(lng, lat)])

                geojson_data["features"].append({
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [lng, lat]
                    },
                    "properties": {
                        "date": event["date"],
                        "venue": event["venue"],
                        "address": event["address"],
                        "city_state_zip": event["city_state_zip"]
                    }
                })
            except Exception as e:
                logging.error(f"❌ Geocoding error: {e}")

        # Save files to memory instead of disk
        kml_output = io.BytesIO()
        kml.save(kml_output)
        kml_output.seek(0)

        geojson_output = io.BytesIO()
        geojson_output.write(json.dumps(geojson_data).encode('utf-8'))
        geojson_output.seek(0)

        # Store files in global variables for download
        global kml_file, geojson_file
        kml_file, geojson_file = kml_output, geojson_output

        return jsonify({
            "status": "success",
            "message": "Scraping completed!",
            "events": events,
            "kml_url": "/download_kml",
            "geojson_url": "/download_geojson"
        })

    except Exception as e:
        logging.error(f"❌ Unhandled error: {e}")
        return jsonify({"status": "error", "message": str(e)})

@app.route('/download_kml')
def download_kml():
    """Download KML file."""
    if kml_file:
        return send_file(kml_file, mimetype='application/vnd.google-earth.kml+xml', as_attachment=True, download_name="events.kml")
    return jsonify({"status": "error", "message": "KML file not found!"}), 404

@app.route('/download_geojson')
def download_geojson():
    """Download GeoJSON file."""
    if geojson_file:
        return send_file(geojson_file, mimetype='application/json', as_attachment=True, download_name="events.geojson")
    return jsonify({"status": "error", "message": "GeoJSON file not found!"}), 404

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
