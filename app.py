import os
import time
import json
import requests
import simplekml
import yagmail
import googlemaps
from flask import Flask, render_template, request, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

app = Flask(__name__)

# Initialize Google Maps API
GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY')  # Ensure API Key is set in Heroku
gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

@app.route('/')
def index():
    """Render the home page."""
    return render_template('index.html')

@app.route('/upload_urls', methods=['POST'])
def upload_urls():
    """Upload multiple URLs."""
    try:
        urls = request.json.get('urls')
        if not urls or not isinstance(urls, list):
            return jsonify({"status": "error", "message": "Invalid URL list"}), 400
        
        with open("urls.txt", "a") as file:
            for url in urls:
                file.write(url + "\n")
        
        return jsonify({"status": "success", "message": "URLs successfully uploaded!"})
    
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/view_urls', methods=['GET'])
def view_urls():
    """Fetch and return stored URLs."""
    try:
        if os.path.exists("urls.txt"):
            with open("urls.txt", "r") as f:
                urls = f.read().splitlines()
            return jsonify({"status": "success", "urls": urls})
        else:
            return jsonify({"status": "error", "message": "No URLs found"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/clear_urls', methods=['POST'])
def clear_urls():
    """Delete all stored URLs."""
    try:
        if os.path.exists("urls.txt"):
            os.remove("urls.txt")
            return jsonify({"status": "success", "message": "URLs cleared successfully"})
        else:
            return jsonify({"status": "error", "message": "No URLs found"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/start_scraping', methods=['POST'])
def start_scraping():
    """Scrape the event details from uploaded URLs."""
    try:
        # Load URLs
        if not os.path.exists("urls.txt"):
            return jsonify({"status": "error", "message": "No URLs found"}), 400
        
        with open("urls.txt", "r") as file:
            urls = file.read().splitlines()
        
        if not urls:
            return jsonify({"status": "error", "message": "No URLs available for scraping"}), 400
        
        # Configure Selenium WebDriver
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        
        driver_path = os.getenv('CHROMEDRIVER_PATH', '/app/.chromedriver/bin/chromedriver')
        browser = webdriver.Chrome(options=chrome_options)
        
        events = []

        for url in urls:
            browser.get(url)
            time.sleep(3)  # Allow page to load
            
            try:
                event_data = {
                    "date": browser.find_element(By.CSS_SELECTOR, "h2.EfW1v6YNlQnbyB7fUHmR").text,
                    "venue": browser.find_element(By.CSS_SELECTOR, "a.q1Vlsw1cdclAUZ4gBvAn").text,
                    "address": browser.find_element(By.CSS_SELECTOR, "div").text,  # Modify if needed
                    "city_state": browser.find_element(By.CSS_SELECTOR, "a[href*='/c/']").text,
                    "zip": browser.find_element(By.CSS_SELECTOR, "div > a[href*='/c/']").text.split()[-1],
                    "url": url
                }
                
                # Get latitude & longitude from Google Maps API
                full_address = f"{event_data['address']}, {event_data['city_state']} {event_data['zip']}"
                geocode_result = gmaps.geocode(full_address)
                
                if geocode_result:
                    location = geocode_result[0]['geometry']['location']
                    event_data["latitude"] = location["lat"]
                    event_data["longitude"] = location["lng"]
                
                events.append(event_data)
            
            except Exception as e:
                print(f"Error scraping {url}: {e}")
        
        browser.quit()

        if not events:
            return jsonify({"status": "error", "message": "No valid event data found."})

        # Generate KML & GeoJSON
        kml = simplekml.Kml()
        geojson_data = {"type": "FeatureCollection", "features": []}

        for event in events:
            if "latitude" in event and "longitude" in event:
                kml.newpoint(
                    name=event["venue"], 
                    description=f"{event['date']} - {event['address']}, {event['city_state']} {event['zip']}",
                    coords=[(event["longitude"], event["latitude"])]
                )

                geojson_data["features"].append({
                    "type": "Feature",
                    "properties": {
                        "name": event["venue"],
                        "date": event["date"],
                        "address": event["address"],
                        "city_state": event["city_state"],
                        "zip": event["zip"],
                    },
                    "geometry": {
                        "type": "Point",
                        "coordinates": [event["longitude"], event["latitude"]]
                    }
                })

        kml_file = "events.kml"
        geojson_file = "events.geojson"
        kml.save(kml_file)

        with open(geojson_file, "w") as f:
            json.dump(geojson_data, f)

        # Send email with attachments
        yag = yagmail.SMTP(os.getenv('EMAIL_USER'), os.getenv('EMAIL_PASS'))
        yag.send(
            to='troyburnsfamily@gmail.com',
            subject='Event Data Files',
            contents='Attached are the event data files.',
            attachments=[kml_file, geojson_file]
        )

        return jsonify({"status": "success", "message": "Scraping completed successfully!", "events": events})

    except Exception as e:
        print(f"Unhandled error: {e}")
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
