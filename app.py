from flask import Flask, render_template, request, session, redirect, url_for, send_file
from PIL import Image

import os
import secrets
import uuid
import hashlib
import pymysql.cursors
from functools import wraps
import time

SALT = "cs3083"

app = Flask(__name__)
app.secret_key = "super secret key"
IMAGES_DIR = os.path.join(os.getcwd(), "images")

connection = pymysql.connect(host="localhost",
                             user="root",
                             password="root",
                             db="Finsta",
                             charset="utf8mb4",
                             port=8889,
                             cursorclass=pymysql.cursors.DictCursor,
                             autocommit=True)
def login_required(f):
    @wraps(f)
    def dec(*args, **kwargs):
        if not "username" in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return dec

@app.route("/")
def index():
    if "username" in session:
        return redirect(url_for("home"))
    return render_template("index.html")

@app.route("/home")
@login_required
def home():
    return render_template("home.html", username=session['username'])

@app.route('/images', methods=["GET"])
@login_required
def images():

    username = session["username"]
    # get the users information
    cursor = connection.cursor()
    query = 'SELECT * FROM Person WHERE username = %s'
    cursor.execute(query, (username))
    data = cursor.fetchone()
    firstName = data["firstName"]
    lastName = data["lastName"]
    # get the photos visible to the username
    query = 'SELECT photoID,postingdate,filepath,caption,photoPoster FROM photo WHERE photoPoster = %s OR photoID IN (SELECT photoID FROM Photo WHERE photoPoster != %s AND allFollowers = 1 AND photoPoster IN (SELECT username_followed FROM follow WHERE username_follower = %s AND username_followed = photoPoster AND followstatus = 1)) OR photoID IN (SELECT photoID FROM sharedwith NATURAL JOIN belongto NATURAL JOIN photo WHERE member_username = %s AND photoPoster != %s) ORDER BY postingdate DESC'
    cursor.execute(query, (username, username, username, username, username))
    data = cursor.fetchall()
    for post in data:  # post is a dictionary within a list of dictionaries for all the photos
        query = 'SELECT username, firstName, lastName FROM tagged NATURAL JOIN person WHERE tagstatus = 1 AND photoID = %s'
        cursor.execute(query, (post['photoID']))
        result = cursor.fetchall()
        print('hello')
        if (result):
            post['tagees'] = result
        query = 'SELECT firstName, lastName FROM person WHERE username = %s'
        cursor.execute(query, (post['photoPoster']))
        ownerInfo = cursor.fetchone()
        post['firstName'] = ownerInfo['firstName']
        post['lastName'] = ownerInfo['lastName']

    cursor.close()
    return render_template('images.html', posts=data)



@app.route("/tag", methods=["GET", "POST"])
@login_required
def tag():
    return render_template(url_for("tag.html"))


@app.route("/upload", methods=["GET"])
@login_required
def upload():
    username = session["username"]
    return render_template("upload.html", username=username)


@app.route("/image/<image_name>", methods=["GET"])
def image(image_name):
    image_location = os.path.join(IMAGES_DIR, image_name)
    if os.path.isfile(image_location):
        return send_file(image_location, mimetype="image/jpg")


# Define route for login
@app.route('/login')
def login():
    return render_template('login.html')


# Define route for register
@app.route('/register')
def register():
    return render_template('register.html')


# Authenticates the login
@app.route('/loginAuth', methods=['GET', 'POST'])
def loginAuth():
    # grabs information from the forms
    # username = request.form['username']
    # password = request.form['password']

    username = request.form['username']
    password = request.form['password'] + SALT
    hashed_password = hashlib.sha256(password.encode('utf-8')).hexdigest()

    # cursor used to send queries
    cursor = connection.cursor()
    # executes query
    query = 'SELECT * FROM person WHERE username = %s and password = %s'
    cursor.execute(query, (username, hashed_password))
    # stores the results in a variable
    data = cursor.fetchone()
    # use fetchall() if you are expecting more than 1 data row
    cursor.close()
    error = None
    if (data):
        # creates a session for the the user
        # session is a built in
        session['username'] = username
        return redirect(url_for('home'))
    else:
        # returns an error message to the html page
        error = 'Invalid login or username'
        return render_template('login.html', error=error)


# Authenticates the register
@app.route('/registerAuth', methods=['GET', 'POST'])
def registerAuth():
    # grabs information from the forms
    username = request.form['username']
    password = request.form['password'] + SALT
    hashed_password = hashlib.sha256(password.encode('utf-8')).hexdigest()
    firstName = request.form['fname']
    lastName = request.form['lname']

    # cursor used to send queries
    cursor = connection.cursor()
    # executes query
    query = 'SELECT * FROM person WHERE username = %s'
    cursor.execute(query, (username))
    # stores the results in a variable
    data = cursor.fetchone()
    # use fetchall() if you are expecting more than 1 data row
    error = None
    if (data):
        # If the previous query returns data, then user exists
        error = 'This user already exists'
        return render_template('register.html', error=error)
    else:
        ins = 'INSERT INTO person (username, password, firstName, lastName) VALUES(%s, %s, %s, %s)'
        cursor.execute(ins, (username, hashed_password, firstName, lastName))
        connection.commit()
        cursor.close()
        return render_template('index.html')

@app.route("/logout", methods=["GET"])
def logout():
    session.pop("username")
    return redirect("/")

def savePhoto(form_picture):
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(app.root_path, 'static/images', picture_fn)
    output_size = (400, 500)
    i = Image.open(form_picture)
    i.thumbnail(output_size)
    i.save(picture_path)

    return picture_fn

@app.route("/uploadImage", methods=["GET", "POST"])
@login_required
def upload_image():
    allFollowers = 0

    if request.files:
        image_file = request.files.get("imageToUpload", "")
        caption = request.form["caption"]
        filepath = savePhoto(image_file)
        username = session["username"]

        if (request.form["allFollowers"] == "True"):
            allFollowers = 1

        query = "INSERT INTO Photo (postingdate, filepath, allFollowers, caption, photoPoster) VALUES (%s, %s, %s, %s, %s)"
        with connection.cursor() as cursor:
            cursor.execute(query, (time.strftime('%Y-%m-%d %H:%M:%S'), filepath, allFollowers, caption, username))
        message = "Image has been successfully uploaded."
        return render_template("upload.html", message=message)
    else:
        message = "Failed to upload image."
        return render_template("upload.html", message=message)

@app.route("/follow", methods=["GET", "POST"])
@login_required
def follow():
    if request.form:
        username = request.form['username']

        # cursor used to send queries
        cursor = connection.cursor()
        # executes query
        query = 'SELECT * FROM person WHERE username = %s'
        cursor.execute(query, (username))
        # stores the results in a variable
        data = cursor.fetchone()
        # use fetchall() if you are expecting more than 1 data row

        error = None
        if (data): # if there is username with given "username"
            query = "SELECT * FROM follow WHERE username_followed = %s AND username_follower = %s"
            cursor.execute(query, (username, session['username']))
            data = cursor.fetchone()
            if (data):
                if (data["followstatus"] == 1):
                    error = "You are already following this user"
                else:
                    error = "Request is still pending"
                return render_template("follow.html", message=error)
            else:
                query = "INSERT INTO follow VALUES(%s, %s, 0)"
                connection.commit()
                cursor.execute(query, (username, session['username']))
                message = "Successfully sent follow request"
                return render_template("follow.html", message = message)
        else:
            # returns an error message to the html page
            error = 'Invalid username'
        cursor.close()
        return render_template('follow.html', message = error)
    return render_template('follow.html')

@app.route("/manageRequests", methods=["GET","POST"])
@login_required
def manageRequests():
    # get all the requests that have followstatus = 0 for the current user
    cursor = connection.cursor()
    query = "SELECT username_follower FROM follow WHERE username_followed = %s"
    cursor.execute(query, (session["username"]))
    data = cursor.fetchall()
    if request.form:
        pass
        # handle form goes here
    cursor.close()
    return render_template("manageRequests.html", followers = data)



if __name__ == "__main__":
    if not os.path.isdir("images"):
        os.mkdir(IMAGES_DIR)
    app.run(debug=True)