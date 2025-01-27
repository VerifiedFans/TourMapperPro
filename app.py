from flask import Flask, render_template, request, jsonify
import requests
import os

app = Flask(__name__)

# Bandsintown API app ID
APP_ID = "your_app_id_here"  # Replace with your actual Bandsintown App ID


def get_artist_events(artist_name, date_filter="all"):
    """
    Fetch events (past or upcoming) for a given artist from the Bandsintown API.
    """
    url = f"https://rest.bandsintown.com/artists/{artist_name}/events/?date={date_filter}&app_id={APP_ID}"
    headers = {
        "User-Agent": "YourApp/1.0 (https://yourwebsite.com)"
    }
    try:
        print(f"Fetching {date_filter} events for artist: {artist_name}")
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Error fetching events: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Error: {e}")
        return None


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

    if not artist_url:
        return jsonify({'status': 'error', 'message': 'Artist URL is required'}), 400
    if not email:
        return jsonify({'status': 'error', 'message': 'Email is required'}), 400

    # Extract artist name from the provided URL
    artist_name = artist_url.split('/')[-1].split('?')[0]
    print("Artist URL received:", artist_url)
    print("Extracted Artist Name:", artist_name)
    print("Email received:", email)

    try:
        # Fetch past events using the Bandsintown API
        past_events = get_artist_events(artist_name, date_filter="past")

        # Check if events were retrieved
        if not past_events:
            return jsonify({'status': 'error', 'message': 'No past events found or API error'}), 404

        # Prepare a list of venues and dates for email
        events_list = "\n".join([f"{event['venue']['name']} - {event['datetime']}" for event in past_events])

        # Placeholder for email logic
        print(f"Sending email to {email} with the following events:\n{events_list}")

        return jsonify({
            'status': 'success',
            'message': 'Process completed successfully!',
            'events': past_events
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)
