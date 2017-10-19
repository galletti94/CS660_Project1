from flask import Flask, render_template, request, flash, redirect, url_for, session
from flaskext.mysql import MySQL
import os, base64
import time
import numpy as np
import pandas as pd

app = Flask(__name__, template_folder='templates')
#app.config['SESSION_TYPE']= 'memcached'        this is not necessary
#app.config['SECRET_KEY']= 'super secret key'   this is not necessary
db = MySQL()

app.config['MYSQL_DATABASE_USER'] = 'root'
app.config['MYSQL_DATABASE_PASSWORD'] = 'hello123'
app.config['MYSQL_DATABASE_DB'] = 'CS660_webapp'
app.config['MYSQL_DATABASE_HOST'] = '127.0.0.1'
db.init_app(app)

ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif'])

conn = db.connect()
cursor = conn.cursor()


@app.route('/', methods=['POST', 'GET'])
def home():

    #when user is not signed in
    query = 'SELECT photo_id, data, caption FROM photos ORDER BY photo_id DESC LIMIT 25'
    cursor.execute(query)
    all_photos = []
    for item in cursor:
        img = ''.join(list(str(item[1]))[2:-1])
        all_photos.append([item[0], img, item[2]])
    return render_template('index.html', photos=all_photos)

@app.route('/login_page', methods=['POST', 'GET'])
def login_page(message='Please Log In'):
    return render_template('login_page.html', message=message)

@app.route('/signup_page', methods=['POST', 'GET'])
def signup_page(message="Please complete the form to sign up"):
    return render_template('signup_page.html', message=message)

@app.route('/signup', methods=['POST','GET'])
def signup():

    #test password mismatch
    result = request.form
    if result['password1'] != result['password2']:
        return signup("Password Mismatch")

    #need other input checks here (like those in mysql)



    #test account already exists
    email=result['email']
    query = 'SELECT email FROM users'
    cursor.execute(query)
    for item in cursor:
        if item[0] == email:
            return login_page("You may already have an account - please log in")

    #insert data into database
    session['email'] = email
    query = 'INSERT INTO users(email, password, first_name, ' \
            'last_name, DoB, hometown, gender) VALUES (%s, %s, %s, %s, %s, %s, %s)'
    DoB = time.strptime(result['DoB'], '%Y-%m-%d')

    #exception handling here is for potential errors from database insertion
    try:
        cursor.execute(query,
                   (result['email'], result['password1'], result['first_name'], result['last_name'],
                    time.strftime('%Y-%m-%d %H:%M:%S', DoB), result['hometown'], result['gender']))
    except:
        return signup_page("Oops, something went wrong - please try again")

    conn.commit()

    #get id generated by database upon insertion
    query = 'SELECT user_id, email, first_name FROM users'
    cursor.execute(query)
    for item in cursor:
        if result['email'] == item[1]:
            userid = item[0]
            my_name = item[2]
            break

    session['userid'] = userid
    session['my_name'] = my_name
    session['loggedin'] = True
    return view_profile(id=userid)

@app.route('/login', methods=['POST', 'GET'])
def login():

    result = request.form
    email = result['email']
    password = result['password']

    #check user has account
    query = 'SELECT email, password, user_id, first_name FROM users'
    cursor.execute(query)
    if cursor.rowcount == 0:
        return signup_page("No Account with this email and password, would you like to create an account?")

    #check password match
    for item in cursor:
        if item[0] == email:
            if item[1] == password:
                session['userid'] = item[2]
                session['my_name'] = item[3]
                session['loggedin'] = True
                return view_profile(id=item[2])
            else:
                return login_page('Wrong Password')

    return signup_page("No Account with this email and password, would you like to create an account?")

@app.route('/logout', methods=['GET', 'POST'])
def logout():
    session.clear()
    session['loggedin'] = False
    return home()

@app.route('/view_profile/<id>', methods=['POST', 'GET'])
def view_profile(id):

    #get name of the person who's profile you're viewing
    query = 'SELECT user_id, first_name FROM users'
    cursor.execute(query)
    for item in cursor:
        if int(id) == int(item[0]):
            person_name = item[1]

    #get all_photos
    query = 'SELECT photo_id, data, caption FROM photos ORDER BY photo_id DESC LIMIT 25'
    cursor.execute(query)
    all_photos = []
    for item in cursor:
        img = ''.join(list(str(item[1]))[2:-1])
        all_photos.append([item[0], img, item[2]])

    #if you're logged in
    if session.get('loggedin', None):

        #get my name and userid
        userid = session.get('userid', None)
        my_name = session.get('my_name', None)

        if int(userid) == int(id):
            same=True
        else:
            same=False

        return render_template('profile.html', name=person_name, username=my_name, loggedin=session.get('loggedin', None),
                               myprofile=same, userid=userid, id=id, photos=all_photos)

    #otherwise
    return render_template('profile.html', name=person_name, loggedin=False, id=id)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS


@app.route('/upload', methods=['GET', 'POST'])
def upload():
    userid = session.get('userid', None)
    my_name = session.get('my_name', None)
    return render_template('upload.html', username=my_name, userid=userid)


@app.route('/create_album', methods=['GET', 'POST'])
def create_album():

    userid = session.get('userid', None)
    my_name = session.get('my_name', None)

    #insert into database album
    result = request.form
    query = 'INSERT INTO albums(user_id, album_name, DOC) VALUES (%s, %s, %s)'

    #need to figure out how to store current date
    DoC = '2017-10-10'

    cursor.execute(query, (userid, result['album'], DoC))
    conn.commit()
    album_id = cursor.lastrowid

    return render_template('upload_photo.html', album_id=album_id, username=my_name, userid=userid)



@app.route('/upload_photo/<album_id>', methods=['GET', 'POST'])
def upload_photo(album_id):

    userid = session.get('userid', None)
    my_name = session.get('my_name', None)

    # insert into database photos
    query = 'INSERT INTO photos(upid_idx, data, caption) VALUES (%s, %s, %s)'
    cap = request.form['caption']
    image = request.files['img']
    cursor.execute(query, (userid, base64.standard_b64encode(image.read()), cap))
    conn.commit()
    photo_id = int(cursor.lastrowid)

    # insert photoid and albumid into contains
    query = 'INSERT INTO contains(photo_id, album_id) VALUES (%s, %s)'
    cursor.execute(query, (photo_id, album_id))
    conn.commit()

    return render_template('upload_photo.html', album_id=album_id, username=my_name, userid=userid)


@app.route('/view_all_albums/<uploader_id>', methods=['GET', 'POST'])
def view_all_albums(uploader_id):

    query = 'SELECT album_id, album_name, user_id FROM albums'
    cursor.execute(query)
    all_albums = []
    for item in cursor:
        if int(item[2]) == int(uploader_id):
            all_albums.append([item[0], item[1]])

    query = 'SELECT user_id, first_name FROM users'
    cursor.execute(query)
    for item in cursor:
        if int(item[0]) == int(uploader_id):
            uploader_name = item[1]
            break

    if session.get('loggedin', None):
        userid = session.get('userid', None)
        my_name = session.get('my_name', None)

        return render_template('view_all_albums.html', username=my_name, userid=userid, uploader_name=uploader_name,
                               all_albums=all_albums, loggedin=True, uploader_id=uploader_id)

    return render_template('view_all_albums.html', uploader_name=uploader_name,
                           all_albums=all_albums, loggedin=False, uploader_id=uploader_id)


@app.route('/view_album_content/<album_id>', methods=['GET', 'POST'])
def view_album_content(album_id):

    # get the album name and uploader id
    query = 'SELECT album_id, album_name, user_id FROM albums'
    cursor.execute(query)
    for item in cursor:
        if int(item[0]) == int(album_id):
            album_name = item[1]
            uploader_id = item[2]
            break

    # get uploader name
    query = 'SELECT first_name, user_id FROM users'
    cursor.execute(query)
    for item in cursor:
        if int(item[1]) == int(uploader_id):
            uploader_name = item[0]
            break

    # get the photo ids of all photos in that album
    query = 'SELECT photo_id, album_id FROM contains'
    cursor.execute(query)
    all_photoids = []
    for item in cursor:
        if int(item[1]) == int(album_id):
            all_photoids.append(int(item[0]))

    # get photo data from all photos with corresponding ids
    query = 'SELECT photo_id, data, caption FROM photos'
    cursor.execute(query)
    all_photos = []
    for item in cursor:
        if item[0] in all_photoids:
            img = ''.join(list(str(item[1]))[2:-1])
            all_photos.append([item[0], img, item[2]])


    #if logged in
    if session.get('loggedin'):

        userid = session.get('userid', None)
        my_name = session.get('my_name', None)
        return render_template('view_album_content.html', username=my_name, uploader_name=uploader_name, loggedin=True,
                               userid=userid, uploader_id=uploader_id, photos=all_photos, album_id=album_id,
                               album_name=album_name)

    else:
        return render_template('view_album_content.html', uploader_name=uploader_name, loggedin=False,
                               uploader_id=uploader_id, photos=all_photos, album_id=album_id, album_name=album_name)

@app.route('/view_photo/<photo_id>', methods=['GET', 'POST'])
def view_photo(photo_id):

    # get the photo data and caption
    query = 'SELECT photo_id, data, caption FROM photos'
    cursor.execute(query)
    for item in cursor:
        if int(item[0]) == int(photo_id):
            img = ''.join(list(str(item[1]))[2:-1])
            photo = [img, item[2], photo_id]

    #get all comment ids and user id of these comments on this photo
    query = 'SELECT photo_id, comment_id, text, user_id FROM comments'
    cursor.execute(query)
    comments = []
    for item in cursor:
        if int(item[0]) == int(photo_id):
            comments.append([item[3], item[2]])

    all_comments = []

    #get names of all commenters
    query = 'SELECT user_id, first_name FROM users'
    cursor.execute(query)
    all_commenters = []
    for item in cursor:
        if int(item[0]) in all_commenters:
            all_commenters.append([item[0], item[1]])

    for i in range(len(comments)):
        for j in range(len(all_commenters)):
            if comments[i][0] == all_commenters[j][0]:
                all_comments.append([comments[i][0], all_commenters[j][1], comments[i][1]])


    # get the album id that this photo belongs to
    query = 'SELECT photo_id, album_id FROM contains'
    cursor.execute(query)
    for item in cursor:
        if int(item[0]) == int(photo_id):
            album_id = int(item[1])

    # get the album name and uploader id
    query = 'SELECT album_name, album_id, user_id FROM albums'
    cursor.execute(query)
    for item in cursor:
        if int(item[1]) == int(album_id):
            album_name = item[0]
            uploader_id = item[2]
            break

    # get uploader name
    query = 'SELECT first_name, user_id FROM users'
    cursor.execute(query)
    for item in cursor:
        if int(item[1]) == int(uploader_id):
            uploader_name = item[0]
            break

    # if logged in
    if session.get('loggedin'):

        userid = session.get('userid', None)
        my_name = session.get('my_name', None)
        liked = False
        return render_template('view_photo.html', username=my_name, uploader_name=uploader_name, loggedin=True, like=liked,
                               userid=userid, uploader_id=uploader_id, photo=photo, album_id=album_id, album_name=album_name, comments=all_comments)

    else:
        return render_template('view_photo.html', uploader_name=uploader_name, loggedin=False,
                               uploader_id=uploader_id, photo=photo, album_id=album_id, album_name=album_name, comments=all_comments)

@app.route('/comment/<photo_id>', methods=['GET', 'POST'])
def comment(photo_id):
    userid = session.get('userid', None)
    my_name = session.get('my_name', None)

    # insert comment and user id
    query = 'INSERT INTO comments(photo_id, text, comment_date, user_id) VALUES (%s, %s, %s, %s)'

    # need to figure out how to store current date
    DoC = '2017-10-10'

    cursor.execute(query, (photo_id, request.form['comment'], DoC, str(userid)))
    conn.commit()

    return view_photo(photo_id=photo_id)



##########################################################

############ TO BE IMPLEMENTED CORRECTLY #################

##########################################################



@app.route('/visit', methods=['GET', 'POST'])
def visit():
    return render_template('visit.html')

@app.route('/photo_search', methods=['GET', 'POST'])
def photo_search():
    return render_template('photo_search.html')

    return render_template('single_photo.html', comments=[session.get('email', None).split('@')[0], nc])

@app.route('/friend_search', methods=['GET', 'POST'])
def friend_search():
    return render_template('friendsearch.html', name=session.get('email', None).split('@')[0])

@app.route('/search', methods=['GET', 'POST'])
def search():
    return render_template('search.html', name=session.get('email', None).split('@')[0])

@app.route('/friends', methods=['GET', 'POST'])
def friends():
    return render_template('friends.html', name=session.get('email', None).split('@')[0])

@app.route('/friend_add', methods=['GET', 'POST'])
def friend_add(friend):
    return render_template('friend_add.html', name=session.get('email', None).split('@')[0], friend=friend)

@app.route('/friend_delete', methods=['GET', 'POST'])
def friend_delete():
    return render_template('friend_delete.html', name=session.get('email', None).split('@')[0])

@app.route('/friend_list', methods=['GET', 'POST'])
def friend_list():
    return render_template('friend_list.html', name=session.get('email', None).split('@')[0])

@app.route('/people_search', methods=['GET', 'POST'])
def people_search():
    return render_template('people_search.html')

@app.route('/recommendations', methods=['GET', 'POST'])
def recommendations():
    return render_template('recommendations.html')


if __name__=='__main__':
    app.secret_key = os.urandom(100)
    app.run(debug=True)