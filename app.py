from flask import Flask, request, jsonify, render_template, send_from_directory
import logging
import os
import json
import simplekml
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup

app = Flask(__name__, template_folder="templates")

# Enable logging for debugging
logging.basicConfig(level=logging.DEBUG)

# Store URLs in memory (temporary storage)
stored_urls = []

@app.route('/')
def home():
    """Serve the main HTML page."""
    return render_template("index.html")

@app.route('/upload_urls', methods=['POST'])
def upload_urls():
    """Receive and store URLs."""
    try:
        data = request.get_json()
        if not data or 'urls' not in data:
            return jsonify({"message": "Invalid request. No URLs received."}), 400

        urls = data['urls']
        if not isinstance(urls, list) or not all(isinstance(url, str) for url in urls):
            return jsonify({"message": "Invalid data format. Expecting a list of URLs."}), 400

        stored_urls.extend(urls)
        logging.info(f"Stored URLs: {stored_urls}")
        return jsonify({"message": "URLs uploaded successfully!"}), 200

    except Exception as e:
        logging.error(f"Upload URLs error: {str(e)}")
        return jsonify({"message": f"Error: {str(e)}"}), 500

@app.route('/view_urls', methods=['GET'])
def view_urls():
    """Retrieve stored URLs."""
    return jsonify({"urls": stored_urls})

@app.route('/clear_urls', methods=['POST'])
def clear_urls():
    """Clear stored URLs."""
    global stored_urls
    stored_urls = []
    return jsonify({"message": "Stored URLs cleared successfully."})

def generate_kml(events):
    """Generate a KML file from scraped events."""
    kml = simplekml.Kml()
    
    for event in events:
        if "latitude" in event and "longitude" in event:
            kml.newpoint(name=event["title"], coords=[(event["longitude"], event["latitude"])])

    os.makedirs("static", exist_ok=True)  # ✅ Ensure 'static/' exists before saving
    file_path = os.path.join("static", "events.kml")
    kml.save(file_path)
    logging.debug(f"KML file saved at {file_path}")

def generate_geojson(events):
    """Generate a GeoJSON file from scraped events."""
    geojson_data = {
        "type": "FeatureCollection",
        "features": []
    }
    
    for event in events:
        if "latitude" in event and "longitude" in event:
            geojson_data["features"].append({
                "type": "Feature",
                "properties": {"title": event["title"]},
                "geometry": {
                    "type": "Point",
                    "coordinates": [event["longitude"], event["latitude"]]
                }
            })

    os.makedirs("static", exist_ok=True)  # ✅ Ensure 'static/' exists before saving
    file_path = os.path.join("static", "events.geojson")
    with open(file_path, "w") as file:
        json.dump(geojson_data, file, indent=4)
    logging.debug(f"GeoJSON file saved at {file_path}")

@app.route('/start_scraping', methods=['POST'])
def start_scraping():
    """Scrape the stored URLs and generate KML & GeoJSON."""
    try:
        if not stored_urls:
            return jsonify({"message": "No URLs to scrape."}), 400

        results = []

        # Set up Selenium
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        service = Service()
        driver = webdriver.Chrome(service=service, options=chrome_options)

        for url in stored_urls:
            driver.get(url)
            time.sleep(3)  # Allow page to load

            soup = BeautifulSoup(driver.page_source, "html.parser")
            title = soup.find("title").text if soup.find("title") else "No title found"

            # Example - Modify based on the website structure
            latitude, longitude = 37.7749, -122.4194  # Fake data, replace with real values

            event_info = {
                "url": url,
                "title": title,
                "latitude": latitude,
                "longitude": longitude
            }
            results.append(event_info)

        driver.quit()

        # ✅ Generate KML & GeoJSON files
        generate_kml(results)
        generate_geojson(results)

        return jsonify({"message": "Scraping completed!", "data": results})

    except Exception as e:
        logging.error(f"Scraping error: {str(e)}")
        return jsonify({"message": f"Error: {str(e)}"}), 500

@app.route('/static/<path:filename>')
def static_files(filename):
    """Serve static files from the 'static' directory."""
    return send_from_directory('static', filename)

if __name__ == '__main__':
    app.run(debug=True)
