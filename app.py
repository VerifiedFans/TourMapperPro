import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_wtf import FlaskForm
from markupsafe import Markup  # ✅ FIXED: Correct import for Flask 2.x+
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired
import redis
from celery import Celery

# Initialize Flask App
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'supersecretkey')

# Redis & Celery Config
app.config['CELERY_BROKER_URL'] = os.getenv('CELERY_BROKER_URL')
app.config['CELERY_RESULT_BACKEND'] = os.getenv('CELERY_RESULT_BACKEND')

celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)

# Sample Redis connection
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
redis_client = redis.Redis.from_url(redis_url)

# Flask Form
class ExampleForm(FlaskForm):
    name = StringField('Your Name', validators=[DataRequired()])
    submit = SubmitField('Submit')

# Home Route
@app.route('/', methods=['GET', 'POST'])
def index():
    form = ExampleForm()
    if form.validate_on_submit():
        flash(f'Thank you, {form.name.data}!', 'success')
        return redirect(url_for('index'))
    return render_template('index.html', form=form)

# Sample Celery Task
@celery.task
def add_numbers(x, y):
    return x + y

# Run the App
if __name__ == '__main__':
    app.run(debug=True)
