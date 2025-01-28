from flask import Flask, render_template, request, jsonify
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

def scrape_past_events(artist_url):
    """
    Scrape past events from the artist's Bandsintown page using Selenium.
    """
    # Initialize Selenium WebDriver
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # Run in headless mode (no GUI)
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")

    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 10)
    past_events = []

    try:
        # Navigate to the artist's Bandsintown page
        driver.get(artist_url)

        # Wait for the page to load and locate the "Past" tab
        wait.until(EC.presence_of_element_located((By.XPATH, "//a[text()='Past']")))

        # Click the "Past" tab
        past_tab = driver.find_element(By.XPATH, "//a[text()='Past']")
        past_tab.click()

        # Wait for the past events to load
        time.sleep(2)

        # Scrape data with pagination
        while True:
            # Parse the page
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            events = soup.find_all("div", class_="event-item")  # Adjust selector as needed

            for event in events:
                event_data = {
                    "venue": event.find("div", class_="event-venue-name").text.strip(),
                    "date": event.find("div", class_="event-date").text.strip(),
                    "location": event.find("div", class_="event-location").text.strip(),
                }
                past_events.append(event_data)

            # Check for the "Next" button and click if available
            try:
                next_button = driver.find_element(By.XPATH, "//a[text()='Next']")
                next_button.click()
                time.sleep(2)
            except:
                print("No more pages.")
                break

    except Exception as e:
        print(f"Error during scraping: {e}")
    finally:
        driver.quit()

    return past_events

@app.route('/start', methods=['POST'])
def start_process():
    artist_url = request.form.get('artist_url')
    email = request.form.get('email', 'troyburnsfamily@gmail.com')

    # Validate form data
    if not artist_url:
        return jsonify({'status': 'error', 'message': 'Artist URL is required'}), 400
    if not email:
        return jsonify({'status': 'error', 'message': 'Email is required'}), 400

    try:
        # Scrape past events
        past_events = scrape_past_events(artist_url)

        # Return the scraped data in JSON response
        return jsonify({
            'status': 'success',
            'message': 'Process completed successfully!',
            'events': past_events
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
