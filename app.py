from flask import Flask, render_template, request, jsonify
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from yagmail import SMTP

app = Flask(__name__)

# Configure email sender
def send_email(to_email, subject, body):
    sender_email = "your_email@gmail.com"
    sender_password = "your_email_password"  # Use app password for Gmail accounts
    with SMTP(sender_email, sender_password) as yag:
        yag.send(to=to_email, subject=subject, contents=body)

# Scrape past events using pagination
def fetch_past_dates_with_pagination(artist_url):
    past_dates = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36'
    }
    current_url = f"{artist_url}?date=past"
    page = 1

    while current_url:
        try:
            print(f"Fetching page {page} of past events from: {current_url}")
            response = requests.get(current_url, headers=headers)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                events = soup.select('div.some-event-class')  # Replace with actual class
                if not events:
                    break

                for event in events:
                    venue_name = event.select_one('span.venue-name-class').text  # Replace
                    datetime = event.select_one('span.date-time-class').text    # Replace
                    past_dates.append({'venue': {'name': venue_name}, 'datetime': datetime})

                # Check for pagination (replace with actual logic)
                next_page_link = soup.select_one('a.pagination-next-class')  # Replace
                current_url = next_page_link['href'] if next_page_link else None
                page += 1
            else:
                raise Exception(f"Error fetching data: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"Error during pagination: {e}")
            break

    return past_dates

@app.route('/')
def index():
    print("Current Working Directory:", os.getcwd())
    print("Templates Folder Exists:", os.path.isdir("templates"))
    print("Templates Contents:", os.listdir("templates"))
    return render_template('index.html')

@app.route('/start', methods=['POST'])
def start_process():
    artist_url = request.form.get('artist_url')
    email = request.form.get('email', 'troyburnsfamily@gmail.com')

    if not artist_url:
        return jsonify({'status': 'error', 'message': 'Artist URL is required'}), 400
    if not email:
        return jsonify({'status': 'error', 'message': 'Email is required'}), 400

    try:
        print("Fetching past events for:", artist_url)
        past_events = fetch_past_dates_with_pagination(artist_url)
        print("Fetched events:", past_events)

        if not past_events:
            body = "No past events were found for the artist."
        else:
            events_list = "\n".join([f"{event['venue']['name']} - {event['datetime']}" for event in past_events])
            body = f"Here are the past events:\n\n{events_list}"

        # Send email
        send_email(email, "TourMapper Pro - Past Events", body)

        return jsonify({
            'status': 'success',
            'message': 'Process completed successfully!',
            'events': past_events
        })
    except Exception as e:
        print("Error:", e)
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
