from flask import Flask, render_template, request, jsonify
import os

app = Flask(__name__)

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

    try:
        # Fetch all past events with pagination
        past_events = fetch_past_dates_with_pagination(artist_url)

        # Prepare email content
        events_list = "\n".join([f"{event['venue']['name']} - {event['datetime']}" for event in past_events])
        body = f"Here are the past events:\n\n{events_list}"

        # Send the email (ensure send_email is defined)
        send_email(email, "TourMapper Pro - Past Events", body)

        return jsonify({
            'status': 'success',
            'message': 'Process completed successfully!',
            'events': past_events
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
            'status': 'success',
            'message': 'Process completed successfully!',
            'artist_url': artist_url,
            'email': email
     
if __name__ == '__main__':
    app.run(debug=True)
