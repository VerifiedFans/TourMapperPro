import os
import json
from flask import Flask, request, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import yagmail
import simplekml
from werkzeug.utils import secure_filename

app = Flask(__name__)
URLS_FILE = "urls.json"

# Ensure the URL file exists
if not os.path.exists(URLS_FILE):
    with open(URLS_FILE, 'w') as f:
        json.dump([], f)

@app.route('/')
def index():
    """Render the index page."""
    return app.send_static_file('index.html')

@app.route('/get-urls', methods=['GET'])
def get_urls():
    """Return the list of URLs."""
    try:
        with open(URLS_FILE, 'r') as f:
            urls = json.load(f)
        return jsonify({"status": "success", "urls": urls})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/add-url', methods=['POST'])
def add_url():
    """Add a new URL."""
    data = request.get_json()
    url = data.get('url')
    if not url:
        return jsonify({"status": "error", "message": "No URL provided."})
    
    try:
        with open(URLS_FILE, 'r') as f:
            urls = json.load(f)
        if url in urls:
            return jsonify({"status": "error", "message": "URL already exists."})
        urls.append(url)
        with open(URLS_FILE, 'w') as f:
            json.dump(urls, f)
        return jsonify({"status": "success", "message": "URL added successfully."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/delete-url', methods=['POST'])
def delete_url():
    """Delete a URL."""
    data = request.get_json()
    url = data.get('url')
    if not url:
        return jsonify({"status": "error", "message": "No URL provided."})
    
    try:
        with open(URLS_FILE, 'r') as f:
            urls = json.load(f)
        if url not in urls:
            return jsonify({"status": "error", "message": "URL not found."})
        urls.remove(url)
        with open(URLS_FILE, 'w') as f:
            json.dump(urls, f)
        return jsonify({"status": "success", "message": "URL deleted successfully."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/upload-urls', methods=['POST'])
def upload_urls():
    """Upload a JSON file of URLs."""
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No file uploaded."})
    file = request.files['file']
    if file.filename == '':
        return jsonify({"status": "error", "message": "No file selected."})
    if file and file.filename.endswith('.json'):
        try:
            file_path = secure_filename(file.filename)
            file.save(file_path)
            with open(file_path, 'r') as f:
                urls = json.load(f)
            if not isinstance(urls, list):
                return jsonify({"status": "error", "message": "Invalid file format. Must be a list of URLs."})
            with open(URLS_FILE, 'w') as f:
                json.dump(urls, f)
            os.remove(file_path)
            return jsonify({"status": "success", "message": "URLs uploaded successfully."})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)})
    else:
        return jsonify({"status": "error", "message": "Invalid file type. Please upload a .json file."})

@app.route('/scrape', methods=['POST'])
def scrape():
    """Scrape all URLs for data."""
    try:
        with open(URLS_FILE, 'r') as f:
            urls = json.load(f)
        if not urls:
            return jsonify({"status": "error", "message": "No URLs to scrape."})

        # Configure WebDriver
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')

        driver_path = os.getenv('CHROMEDRIVER_PATH', '/app/.chromedriver/bin/chromedriver')
        browser = webdriver.Chrome(driver_path, options=chrome_options)

        events = []
        for url in urls:
            browser.get(url)
            WebDriverWait(browser, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "event"))
            )
            event_elements = browser.find_elements(By.CLASS_NAME, "event")
            for event in event_elements:
                event_data = {
                    "venue": event.find_element(By.CLASS_NAME, "venue").text,
                    "date": event.find_element(By.CLASS_NAME, "date").text,
                    "location": event.find_element(By.CLASS_NAME, "location").text,
                    "url": event.find_element(By.TAG_NAME, "a").get_attribute("href")
                }
                events.append(event_data)

        browser.quit()

        if not events:
            return jsonify({"status": "success", "message": "No events found.", "events": []})

        # Generate KML
        kml = simplekml.Kml()
        for event in events:
            kml.newpoint(name=event['venue'], description=event['date'], coords=[(0, 0)])  # Replace with actual coords

        kml_file = "events.kml"
        kml.save(kml_file)

        # Email the results
        yag = yagmail.SMTP(os.getenv('EMAIL_USER'), os.getenv('EMAIL_PASS'))
        yag.send(
            to='troyburnsfamily@gmail.com',
            subject='Scraped Event Data',
            contents='Attached is the scraped event data in KML format.',
            attachments=[kml_file]
        )

        return jsonify({"status": "success", "message": "Scraping completed.", "events": events})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    app.run(debug=True, host=
