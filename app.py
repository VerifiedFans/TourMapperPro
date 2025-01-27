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

    # Validate form data
    if not artist_url:
        return jsonify({'status': 'error', 'message': 'Artist URL is required'}), 400
    if not email:
        return jsonify({'status': 'error', 'message': 'Email is required'}), 400

    try:
        # Simulated process (replace with actual logic)
        return jsonify({
            'status': 'success',
            'message': 'Process completed successfully!',
            'artist_url': artist_url,
            'email': email
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
if __name__ == '__main__':
    app.run(debug=True)
