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

# Load Google Maps API Key from environment
gmaps = googlemaps.Client(key=os.getenv('GOOGLE_MAPS_API_KEY'))


@app.route('/')
def index():
    """Render the home page."""
    return render_template('index.html')


@app.route('/upload_urls', methods=['POST'])
def upload_urls():
    """Handle URL uploads from user input."""
    data = request.get_json()
    urls = data.get('urls', [])
    if not urls:
        return jsonify({"status": "error", "message": "No URLs provided."}), 400

    # Save URLs to a local file for reference
    with open("venue_urls.txt", "w") as f:
        f.writelines("\n".join(urls))

    return jsonify({"status": "success", "message": "URLs successfully uploaded."})


def scrape_venue_data(browser, url):
    """Scrape event data from a venue page."""
    try:
        browser.get(url)
        time.sleep(2)  # Allow page to load

        venue_name = browser.find_element(By.CSS_SELECTOR, ".venue-name").text
        event_date = browser.find_element(By.CSS_SELECTOR, ".event-date").text
        address = browser.find_element(By.CSS_SELECTOR, ".event-address").text
        city = browser.find_element(By.CSS_SELECTOR, ".event-city").text
        state = browser.find_element(By.CSS_SELECTOR, ".event-state").text
        zip_code = browser.find_element(By.CSS_SELECTOR, ".event-zip").text

        return {
            "venue_name": venue_name,
            "event_date": event_date,
            "address": address,
            "city": city,
            "state": state,
            "zip": zip_code,
            "full_address": f"{address}, {city}, {state} {zip_code}",
        }
    except Exception as e:
        print(f"Error scraping URL {url}: {e}")
        return None


def geocode_address(address):
    """Use Google Maps API to get latitude and longitude from an address."""
    try:
        geocode_result = gmaps.geocode(address)
        if geocode_result:
            location = geocode_result[0]['geometry']['location']
            return location['lat'], location['lng']
        else:
            print(f"No geocode results found for address: {address}")
            return None
    except Exception as e:
        print(f"Geocoding error: {e}")
        return None


@app.route('/start', methods=['POST'])
def start_scraping():
    """Start scraping URLs asynchronously, geocode addresses, and generate KML."""
    try:
        with open("venue_urls.txt", "r") as f:
            urls = f.read().splitlines()

        if not urls:
            return jsonify({"status": "error", "message": "No URLs to scrape."}), 400

        # Configure Chrome WebDriver
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        driver_path = os.getenv('CHROMEDRIVER_PATH', '/app/.chromedriver/bin/chromedriver')
        browser = webdriver.Chrome(options=chrome_options)

        events = []
        for url in urls:
            event_data = scrape_venue_data(browser, url)
            if event_data:
                coords = geocode_address(event_data["full_address"])
                if coords:
                    event_data["latitude"], event_data["longitude"] = coords
                events.append(event_data)

        browser.quit()

        if not events:
            return jsonify({"status": "success", "message": "No valid event data found.", "events": []})

        # Generate KML file
        kml = simplekml.Kml()
        for event in events:
            kml.newpoint(
                name=event["venue_name"],
                description=f"{event['event_date']} - {event['full_address']}",
                coords=[(event["longitude"], event["latitude"])]
            )
        kml_file = "events.kml"
        kml.save(kml_file)

        # Send KML via email
        yag = yagmail.SMTP(os.getenv('EMAIL_USER'), os.getenv('EMAIL_PASS'))
        yag.send(
            to="troyburnsfamily@gmail.com",
            subject="Event Data",
            contents="Attached is the event data.",
            attachments=[kml_file]
        )

        return jsonify({"status": "success", "message": "Scraping completed successfully.", "events": events})

    except Exception as e:
        print(f"Unhandled error: {e}")
        return jsonify({"status": "error", "message": str(e)})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
