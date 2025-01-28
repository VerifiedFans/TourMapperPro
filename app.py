import os
import time
import json
from flask import Flask, render_template, request
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import yagmail
import simplekml

app = Flask(__name__)

@app.route('/')
def index():
    """Render the home page."""
    try:
        print("Current Working Directory:", os.getcwd())
        print("Templates Folder Exists:", os.path.exists("templates"))
        print("Templates Contents:", os.listdir("templates"))
    except Exception as e:
        print(f"Error accessing templates folder: {e}")
    return render_template('index.html')

@app.route('/start', methods=['POST'])
def start():
    """Start scraping for past events."""
    try:
        # Parse request data
        data = request.get_json()
        artist_url = data.get('artist_url')
        if not artist_url:
            return json.dumps({"status": "error", "message": "No artist URL provided."}), 400

        # Configure Chrome WebDriver
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')

        driver_path = os.getenv('CHROMEDRIVER_PATH', '/app/.chromedriver/bin/chromedriver')
        browser = webdriver.Chrome(driver_path, options=chrome_options)

        # Open the artist's page
        browser.get(artist_url)

        # Locate and click the "Past" button
        try:
            past_button = WebDriverWait(browser, 10).until(
                EC.element_to_be_clickable((By.LINK_TEXT, "Past"))
            )
            past_button.click()
        except Exception as e:
            print(f"Error finding or clicking 'Past' button: {e}")
            browser.quit()
            return json.dumps({"status": "error", "message": "Could not navigate to past events."}), 500

        # Scrape past events
        events = []
        while True:
            try:
                time.sleep(2)  # Allow page to load
                event_elements = browser.find_elements(By.CSS_SELECTOR, '.event')

                for event in event_elements:
                    try:
                        event_data = {
                            "date": event.find_element(By.CSS_SELECTOR, '.event-date').text,
                            "venue": event.find_element(By.CSS_SELECTOR, '.event-venue').text,
                            "location": event.find_element(By.CSS_SELECTOR, '.event-location').text,
                            "url": event.find_element(By.CSS_SELECTOR, 'a').get_attribute('href')
                        }
                        events.append(event_data)
                    except Exception as e:
                        print(f"Error extracting event data: {e}")

                # Check for pagination (Show More Dates button)
                show_more_button = browser.find_elements(By.LINK_TEXT, "Show More Dates")
                if show_more_button:
                    show_more_button[0].click()
                    time.sleep(2)  # Allow new events to load
                else:
                    break

            except Exception as e:
                print(f"Error during scraping: {e}")
                break

        browser.quit()

        if not events:
            return json.dumps({"status": "success", "message": "No past events found for this artist.", "events": []})

        # Generate KML and GeoJSON files
        kml = simplekml.Kml()
        for event in events:
            kml.newpoint(name=event['venue'], description=event['date'], coords=[(0, 0)])  # Replace with actual coords if available

        kml_file = "events.kml"
        kml.save(kml_file)

        # Send email with the KML file
        try:
            yag = yagmail.SMTP(os.getenv('EMAIL_USER'), os.getenv('EMAIL_PASS'))
            yag.send(
                to='troyburnsfamily@gmail.com',
                subject='Event Data',
                contents='See attached KML file with event data.',
                attachments=[kml_file]
            )
        except Exception as e:
            print(f"Error sending email: {e}")
            return json.dumps({"status": "error", "message": "Failed to send email."})

        return json.dumps({"status": "success", "message": "Scraping completed successfully.", "events": events})

    except Exception as e:
        print(f"Unhandled error: {e}")
        return json.dumps({"status": "error", "message": str(e)})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
