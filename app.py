import os
import firebase_admin
from firebase_admin import auth
from flask import Flask, request, render_template, jsonify, flash
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from dotenv import load_dotenv 
from wtforms import PasswordField
from wtforms.validators import DataRequired, EqualTo
from flask import Markup
from flask import session
from flask import redirect, url_for
from json import dumps, loads
from bson.json_util import dumps
from pymongo.errors import PyMongoError


# Initialize the Firebase Admin SDK
cred = firebase_admin.credentials.Certificate('testmongo.json')
firebase_admin.initialize_app(cred)

# access your MongoDB Atlas cluster
load_dotenv()
connection_string = os.environ.get('CONNECTION_STRING')
mongo_client: MongoClient = MongoClient(connection_string)

# add in your database and collection from Atlas 
database: Database = mongo_client.get_database('Neuro')
user_collection: Collection = database.get_collection('users')
assessment: Collection = database.get_collection('assessment')
educational_support: Collection = database.get_collection('educational support')
therapy: Collection = database.get_collection('therapy')
mythersaurus: Collection = database.get_collection('thersaurus')

assessment.create_index([("name", "text"), ("keyword", "text")])
educational_support.create_index([("agency", "text"), ("keyword", "text")])
therapy.create_index([("provider", "text"), ("keyword", "text")])
mythersaurus.create_index([("term", "text"),("acronym", "text")])

# instantiating new object with “name”
app: Flask = Flask(__name__)

# our initial form page
@app.route("/")
def index():
    return redirect(url_for('signin'))

app.config['SECRET_KEY'] = "mysecretkey"

# User Registration Form
class SignupForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired()])
    submit = SubmitField('Sign Up')

# User Sign In Form
class SignInForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Sign In')
    
# Entity Registration Form
class RegistrationForm(FlaskForm):
    entity_name = StringField('Entity Name', validators=[DataRequired()])
    rep_name = StringField('Representative Name', validators=[DataRequired()])
    rep_title = StringField('Representative Title', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired()])
    submit = SubmitField('Sign Up')

# Redirect user to their profile page if they are already signed in
@app.before_request
def before_request():
    if 'user' in session and request.endpoint in ['signin', 'signup']:
        return redirect(url_for('user', name=session['user']))
    
# Check if a user is signed in (for debugging purposes)   
@app.route('/check_user', methods=['GET'])
def check_user():
    if 'user' in session:
        return f"User {session['user']} is currently signed in."
    else:
        return "No user is currently signed in."

# Sign in a user
@app.route('/api/signin', methods=['POST'])
def api_signin():
    email = request.json.get('email')
    if email:
        session['user'] = email
        return jsonify({'message': 'User signed in successfully'}), 200
    else:
        return jsonify({'message': 'No email provided'}), 400

# Signup a new user
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    form = SignupForm()

    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data
        confirm_password = form.confirm_password.data
        print(password)
        # Check if the password is at least 6 characters long
        if len(password) < 6 or len(confirm_password) < 6:
            flash('Password must be at least 6 characters long', 'error')
            return render_template('signup.html', title='Sign Up', form=form)

        # Check if the user is already registered
        try:
            user = auth.get_user_by_email(email)
            flash(Markup(f"<strong>Holy guacamole!</strong> You're already registered. Please <a href={url_for('signin')} class='alert-link'>sign in</a>."), 'error')
            return render_template('signup.html', title='Sign Up', form=form)
        except auth.UserNotFoundError:


            # User does not exist, check if the passwords match
            if password != confirm_password:
                flash('Passwords do not match', 'error')
                return render_template('signup.html', title='Sign Up', form=form)

            # Create a new user
            user = auth.create_user(
                email=email,
                password=password
            )
            userdb = {
                'uid': user.uid,
                'name': form.name.data,
                'email': email
            }  
            user_collection.insert_one(userdb)
            
            return redirect(url_for('signin'))

    return render_template('signup.html', title='Sign Up', form=form)

# Sign in a user
@app.route('/signin', methods=['GET', 'POST'])
def signin():
    form = SignInForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data
        try:
            user = auth.get_user_by_email(email)
            if user and user.password == password:  
                # Store user information in session
                session['user'] = {
                    'uid': user.uid,
                    'name': user.name,
                    'email': user.email
                }
                return redirect(url_for('user'))
        except auth.UserNotFoundError:
            # If the user does not exist, flash an error message
            flash('User does not exist', 'error')
    return render_template('signin.html', title='Sign In', form=form)

# Sign out a user
@app.route('/signout', methods=['GET'])
def signout():
    session.pop('user', None)
    return redirect(url_for('signin'))

# Error Handling 404
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

# Error Handling 500
@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

# User Profile Page - only accessible if a user is signed in
@app.route('/user')
def user():
    # Check if user is logged in
    if 'user' not in session:
        return redirect(url_for('signin'))
    # Get user email from session
    user_email = session['user']
    # Query the users collection with the user's email
    user_info = user_collection.find_one({'email': user_email})
    # Convert the user_info document to a JSON string
    user_info_json = dumps(user_info)
    return render_template('user.html', user_info=user_info_json)

@app.route('/services', methods=['GET', 'POST'])
def services():
    query = {}
    if request.method == 'POST':
        search_term = request.form.get('query')
        query = {"$text": {"$search": search_term}}
    assessments = list(assessment.find(query))
    educational_supports = list(educational_support.find(query))
    therapies = list(therapy.find(query))
    # Convert documents to JSON strings and add them to a set to remove duplicates
    assessments = [loads(doc) for doc in set(dumps(doc, default=str) for doc in assessments)]
    educational_supports = [loads(doc) for doc in set(dumps(doc, default=str) for doc in educational_supports)]
    therapies = [loads(doc) for doc in set(dumps(doc, default=str) for doc in therapies)]
    
    print('Assessments:', assessments)
    print('Educational Supports:', educational_supports)
    print('Therapies:', therapies)
    
    # Convert ObjectIds to strings
    for item in assessments:
        item['_id'] = str(item['_id'])
    for item in educational_supports:
        item['_id'] = str(item['_id'])
    for item in therapies:
        item['_id'] = str(item['_id'])
    return render_template('services.html', assessments=assessments, educational_supports=educational_supports, therapies=therapies)

@app.route('/thesaurus', methods=['GET', 'POST'])
def thesaurus_view():
    query = {}
    if request.method == 'POST':
        search_term = request.form.get('query')
        if search_term:
            query = {"$or": [{"term": {"$regex": search_term, "$options": 'i'}}, {"acronym": {"$regex": search_term, "$options": 'i'}}]}
    terms = list(mythersaurus.find(query))
    terms = [loads(doc) for doc in set(dumps(doc, default=str) for doc in terms)]
    terms.sort(key=lambda term: term['term'].strip().lower())
    return render_template('thersaurus.html', terms=terms)

@app.route('/add_term', methods=['POST'])
def add_term():
    term = request.json['term']
    acronym = request.json['acronym']
    definition = request.json['definition']
    print(term)
    mythersaurus.insert_one({"term": term, "acronym": acronym, "definition": definition})

    return f"CREATE: The term {term} ({acronym}) with definition {definition} has been added.\n"


# Register a new entity
@app.route("/register", methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        flash('Account created for {form.email.data}!', 'success')
        return redirect(url_for('home'))
    return render_template('register.html', title='Register', form=form)
