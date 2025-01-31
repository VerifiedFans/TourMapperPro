from flask import Flask, request, jsonify, render_template
import logging
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup

app = Flask(__name__, template_folder="templates")

# Enable logging for debugging
logging.basicConfig(level=logging.DEBUG)

# Store URLs in memory (temporary)
stored_urls = []

@app.route('/')
def home():
    """Serve the main HTML page."""
    return render_template("index.html")  # ✅ Ensure index.html is in the 'templates' folder

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

@app.route('/start_scraping', methods=['POST'])
def start_scraping():
    """Scrape the stored URLs using Selenium & BeautifulSoup."""
    try:
        if not stored_urls:
            return jsonify({"message": "No URLs to scrape."}), 400

        results = []

        # Set up Selenium (Chromedriver for Heroku)
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Run in headless mode (no UI)
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        service = Service()  # Let Selenium find chromedriver automatically
        driver = webdriver.Chrome(service=service, options=chrome_options)

        for url in stored_urls:
            driver.get(url)
            time.sleep(3)  # Allow page to load

            soup = BeautifulSoup(driver.page_source, "html.parser")

            # Extract relevant data (Modify based on site structure)
            title = soup.find("title").text if soup.find("title") else "No title found"
            event_info = {
                "url": url,
                "title": title
            }
            results.append(event_info)

        driver.quit()  # Close the browser

        return jsonify({"message": "Scraping completed!", "data": results})

    except Exception as e:
        logging.error(f"Scraping error: {str(e)}")
        return jsonify({"message": f"Error: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True)
