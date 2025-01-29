import os
import time
import json
import yagmail
import simplekml
import googlemaps
from flask import Flask, render_template, request, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

app = Flask(__name__)

# Initialize Google Maps API
gmaps = googlemaps.Client(key=os.getenv('GOOGLE_MAPS_API_KEY'))

@app.route('/')
def index():
    """Render the home page."""
    return render_template('index.html')

@app.route('/upload_urls', methods=['POST'])
def upload_urls():
    """Upload and store URLs."""
    try:
        urls = request.get_json().get('urls', [])
        if not urls:
            return jsonify({"status": "error", "message": "No URLs provided"}), 400
        
        with open("urls.txt", "w") as f:
            f.write("\n".join(urls))
        
        return jsonify({"status": "success", "message": "URLs saved successfully"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/start_scraping', methods=['POST'])
def start_scraping():
    """Scrape venue data from uploaded URLs."""
    try:
        # Load URLs from file
        with open("urls.txt", "r") as f:
            urls = f.read().splitlines()

        if not urls:
            return jsonify({"status": "error", "message": "No URLs found"})

        # Configure Selenium WebDriver
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        driver_path = os.getenv('CHROMEDRIVER_PATH', '/app/.chromedriver/bin/chromedriver')
        browser = webdriver.Chrome(driver_path, options=chrome_options)

        events = []
        for url in urls:
            browser.get(url)
            time.sleep(2)  # Allow page to load

            try:
                event_date = browser.find_element(By.CSS_SELECTOR, 'h2.EfW1v6YNlQnbyB7fUHmR').text
                venue_name = browser.find_element(By.CSS_SELECTOR, 'a.q1Vlsw1cdclAUZ4gBvAn').text
                city_state_element = browser.find_element(By.CSS_SELECTOR, 'a[href*="bandsintown.com/c/"]')
                city_state = city_state_element.text
                zip_code = city_state_element.find_element(By.XPATH, './following-sibling::div').text
                address = browser.find_element(By.XPATH, '//*[text()="Address"]/following-sibling::div').text

                # Separate city and state
                city, state = city_state.split(", ")
                
                # Geocode using Google Maps API
                full_address = f"{address}, {city}, {state} {zip_code}"
                geocode_result = gmaps.geocode(full_address)
                if geocode_result:
                    lat = geocode_result[0]['geometry']['location']['lat']
                    lng = geocode_result[0]['geometry']['location']['lng']
                else:
                    lat, lng = None, None

                # Store event data
                event_data = {
                    "date": event_date,
                    "venue": venue_name,
                    "address": address,
                    "city": city,
                    "state": state,
                    "zip": zip_code,
                    "latitude": lat,
                    "longitude": lng
                }
                events.append(event_data)
            except Exception as e:
                print(f"Error scraping {url}: {e}")
                continue

        browser.quit()

        if not events:
            return jsonify({"status": "error", "message": "No valid event data found"})

        # Generate KML file
        kml = simplekml.Kml()
        for event in events:
            if event["latitude"] and event["longitude"]:
                kml.newpoint(
                    name=event["venue"],
                    description=f"{event['date']}, {event['address']}, {event['city']}, {event['state']} {event['zip']}",
                    coords=[(event["longitude"], event["latitude"])]
                )

        kml_file = "events.kml"
        kml.save(kml_file)

        # Send email
        yag = yagmail.SMTP(os.getenv('EMAIL_USER'), os.getenv('EMAIL_PASS'))
        yag.send(to='troyburnsfamily@gmail.com', subject='Event Data', contents='See attached.', attachments=[kml_file])

        return jsonify({"status": "success", "message": "Scraping completed successfully.", "events": events})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
