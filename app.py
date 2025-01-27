from flask import Flask, render_template, request, jsonify
import os
import requests

app = Flask(__name__)

def fetch_past_dates_with_pagination(artist_url):
    """
    Fetch past tour dates from Bandsintown using pagination.
    Includes a custom User-Agent header to avoid being blocked.
    """
    past_dates = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    current_url = f"{artist_url}?date=past"
    page = 1

    while current_url:
        try:
            print(f"Fetching page {page} of past events from: {current_url}")
            response = requests.get(current_url, headers=headers)

            if response.status_code == 200:
                data = response.json()
                if not data:
                    break  # No more data, stop pagination
                past_dates.extend(data)

                # Update current_url to the next page if pagination is supported
                # This logic assumes pagination links are in the response headers
                current_url = response.links.get('next', {}).get('url')
                page += 1
            else:
                raise Exception(f"Error fetching data: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"Error during pagination: {e}")
            break

    return past_dates

@app.route('/')
def index():
    # Debugging output to verify the templates folder
    print("Current Working Directory:", os.getcwd())
    print("Templates Folder Exists:", os.path.isdir("templates"))
    print("Templates Contents:", os.listdir("templates"))
    return render_template('index.html')

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
        # Fetch all past events with pagination
        past_events = fetch_past_dates_with_pagination(artist_url)

        # Prepare email content (replace send_email function with actual implementation)
        events_list = "\n".join([f"{event['venue']['name']} - {event['datetime']}" for event in past_events])
        print("Collected Events:", events_list)
        
        return jsonify({
            'status': 'success',
            'message': 'Process completed successfully!',
            'events': past_events
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
