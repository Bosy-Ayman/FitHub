# importing necessary libraries
from flask import Flask, render_template, request, session, flash, redirect, url_for, send_file, jsonify
from io import BytesIO
import sqlite3
import random
from datetime import datetime
from flask_mail import Mail, Message
import numpy as np
import base64
import ast
import os
from authlib.integrations.flask_client import OAuth
from flask_bcrypt import Bcrypt
import tempfile

# database path
DATABASE = 'FitHub_DB.sqlite'

# app initialization
app = Flask(__name__)
app.secret_key = 'suchasecurekey'
bcrypt = Bcrypt(app)

# oauth config
app.config['SERVER_NAME'] = '127.0.0.1:5000'
oauth = OAuth(app)

GOOGLE_CLIENT_ID = "182040310616-60khtr7cc6mp3ji72ceut8tsivccmrui.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "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"
CONF_URL = 'https://accounts.google.com/.well-known/openid-configuration'

oauth.register(
    name='google',
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url=CONF_URL,
    client_kwargs={
        'scope': 'openid email profile'
    }
)

co_email = "s-farha.shady@zewailcity.edu.eg"
co_pw = "7ThuKc?C"


# function to connect to database
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def photo_to_binary(img):
    with open(img, 'rb') as f:
        image_data = base64.b64encode(f.read()).decode('utf-8')
    return image_data


def serve_image(table, table_id):
    conn = get_db_connection()
    if table == "User":
        query = f'SELECT Profile_picture FROM {table} WHERE User_ID = ?'
    else:
        tid = table + "_ID"
        query = f'SELECT Media FROM {table} WHERE {tid} = ?'
    image_data = conn.execute(query, (table_id,)).fetchone()
    conn.close()
    # return default profile photo if user hasn't uploaded a profile picture
    if table == "User":
        if image_data is None or image_data[0] is None:
            return 'static/default_profile.jpg'
    if table == "Recipe":
        if image_data is None or image_data[0] is None:
            return 'static/default_recipe.jpg'
    if image_data is None or image_data[0] is None:
        return None
    # change string into base64 to be read properly
    if isinstance(image_data[0], str):
        image_data = base64.b64decode(image_data[0])
        base64_image = base64.b64encode(image_data).decode('utf-8')
        return f"data:image/jpeg;base64,{base64_image}"
    if isinstance(image_data[0], bytes):
        base64_image = base64.b64encode(image_data[0]).decode('utf-8')
        return f"data:image/jpeg;base64,{base64_image}"
    # send image
    return send_file(BytesIO(image_data), mimetype='image/jpg', as_attachment=False)


def send_email(rcvr, subject, content):
    app.config['MAIL_SERVER'] = 'smtp.gmail.com'
    app.config['MAIL_PORT'] = 465
    app.config['MAIL_USERNAME'] = co_email
    app.config['MAIL_PASSWORD'] = co_pw
    app.config['MAIL_USE_TLS'] = False
    app.config['MAIL_USE_SSL'] = True
    mail = Mail(app)
    msg = Message(subject, sender=co_email, recipients=[rcvr])
    msg.body = content
    mail.send(msg)


# load homepage
@app.route('/', methods=['GET', 'POST'])
def home_page():
    # check if a user is logged in
    if 'User_ID' in session:
        User_ID = session['User_ID']
        # returns logged-in user from the database
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM User WHERE User_ID = ?', (User_ID,)).fetchone()
        conn.close()
        img = serve_image("User", user[0])
        # send the user to the homepage
        return render_template("homepage.html", user=user, img=img)
    # if there's no user logged in, redirects them to the login page
    return redirect(url_for('login'))


# sign up page where the new user decides if they're a coach or a trainee to
# get redirected to the appropriate sign-up page
@app.route('/signUp', methods=['GET', 'POST'])
def role_choice():
    if request.method == 'POST':
        print("POST request received")
        print("Request form data:", request.form)
        print("Request data:", request.data)
        print("Session before update:", session)
        session["role"] = request.form.get("role")
        if session["role"] == "Trainee":
            return redirect(url_for("traineeSignUp"))
        elif session["role"] == "Coach":
            return redirect(url_for("coachSignUp"))
    return render_template("role.html")


# login page
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # save email & password entered
        Email = request.form['Email']
        password = request.form['password']

        # save user if a user with teh entered email and password exists
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM User WHERE Email = ?',
                            (Email,)).fetchone()
        pw_hash = user[3]
        pw_flag = bcrypt.check_password_hash(pw_hash, password)
        conn.close()
        # if a user is found save the id in the session to be used across pages
        if user and pw_flag:
            session['User_ID'] = user[0]
            return redirect(url_for('redirectPerRole'))
        # if user isn't found a message is shown to inform that the credentials are invalid
        else:
            flash('Invalid email or password', 'danger')

    return render_template("login.html")


@app.route('/personal_profile', methods=['GET', 'POST'])
def personalProfile():
    conn = get_db_connection()
    role = conn.execute('SELECT Role FROM User WHERE User_ID = ?',
                        (session["User_ID"],)).fetchone()
    conn.close()
    if role[0] == "Trainee":
        return redirect(url_for("personalProfileTraineeStats"))
    elif role[0] == "Coach":
        return redirect(url_for("personalProfileCoachInformation"))
    else:
        return redirect(url_for("home_page"))


@app.route('/editProfileTrainee', methods=['GET', 'POST'])
def editProfileTrainee():
    conn = get_db_connection()
    gen_info = conn.execute('SELECT * FROM User WHERE User_ID = ?', (session["User_ID"],)).fetchone()
    trainee_info = conn.execute('SELECT * FROM Trainee WHERE Trainee_ID = ?', (session["User_ID"],)).fetchone()
    all_interests = conn.execute('SELECT * FROM Interest').fetchall()
    conn.close()
    if request.method == 'POST':
        pfp_file = request.files['pfp']
        username = request.form['username']
        pw = request.form['password']
        age = request.form['age']
        height = request.form['height']
        weight = request.form['weight']
        bmi = round(int(weight) / (float(height) ** 2), 2)
        interests_id = request.form.getlist('interests')

        conn = get_db_connection()
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(pfp_file.read())
            temp_file_path = temp_file.name
        pfp = photo_to_binary(temp_file_path)
        os.remove(temp_file_path)
        interests = ""
        for intr in interests_id:
            inter = conn.execute('SELECT Name FROM Interest WHERE Interest_ID = ?', (intr,)).fetchone()
            interests += inter[0] + ","
        interests = interests[:-1]
        if pfp_file:
            conn.execute('UPDATE User SET Profile_picture=?, Name=?, Password=?, Age=?, Interests=? WHERE User_ID=?',
                         (pfp, username, pw, age, interests, session["User_ID"]))
        else:
            conn.execute('UPDATE User SET Name=?, Password=?, Age=?, Interests=? WHERE User_ID=?',
                         (username, pw, age, interests, session["User_ID"]))
        print(weight, height, bmi, round(float(54) / (float(162) ** 2), 2))
        conn.execute('UPDATE Trainee SET Weight_kg=?, Height_m=?, BMI=? WHERE Trainee_ID=?',
                     (weight, height, str(bmi), session["User_ID"]))
        conn.commit()
        conn.close()
        return redirect(url_for("personalProfileTraineeStats"))

    return render_template("edit_profile_trainee.html", gen_info=gen_info, trainee_info=trainee_info,
                           interests=all_interests)


@app.route('/profileTraineeStats', methods=['GET', 'POST'])
def personalProfileTraineeStats():
    conn = get_db_connection()
    trainee = True
    role = conn.execute('SELECT Role FROM User WHERE User_ID = ?', (session["User_ID"],)).fetchone()
    if role == "Coach":
        trainee = False
    gen_info = conn.execute('SELECT * FROM User WHERE User_ID = ?', (session["User_ID"],)).fetchone()
    trainee_info = conn.execute('SELECT * FROM Trainee WHERE Trainee_ID = ?', (session["User_ID"],)).fetchone()
    today = datetime.now().strftime("%Y-%m-%d")
    today = str(today)
    exercises_list = conn.execute('SELECT * FROM Trainee_Exercise WHERE Trainee_ID = ? AND Timestamp = ?',
                                  (session["User_ID"], today)).fetchall()
    workout_time = 0
    exercises = []
    if exercises_list:
        exercise_flag = True
        exercises_id = exercises_list[0][1].split(",")
        for eid in exercises_id:
            photo = serve_image("Exercise", eid)
            e = conn.execute('SELECT Name, Duration FROM Exercise WHERE Exercise_ID = ?', (eid,)).fetchall()
            exercises.append([e[0][0], photo, e[0][1]])
        for exercise in exercises:
            workout_time += int(exercise[2])
    else:
        exercise_flag = False
    nutrition = conn.execute('SELECT * FROM Trainee_Recipes WHERE Trainee_ID = ? AND Timestamp = ?',
                             (session["User_ID"], today)).fetchall()
    conn.close()
    if nutrition:
        nutrition = nutrition[0]
        nutrition_flag = True
    else:
        nutrition = []
        nutrition_flag = False
    pfp = serve_image("User", session["User_ID"])
    workout_time = round(workout_time / 3600, 2)

    if request.method == 'POST':
        data = request.get_json()
        if not data or 'number' not in data:
            return jsonify({'message': 'No time entered'}), 400
        number = data['number']
        # Example of processing the number if needed
        workout_time += float(number) / 60
        print(workout_time)
        return jsonify({'message': 'Success', 'new_workout_time': workout_time})

    return render_template("personal_profile_trainee_stats.html", gen_info=gen_info, pfp=pfp,
                           trainee_info=trainee_info, exercises=exercises, workout_time=workout_time,
                           nutrition=nutrition, trainee=trainee, exercise_flag=exercise_flag,
                           nutrition_flag=nutrition_flag)


@app.route('/profileTraineePosts', methods=['GET', 'POST'])
def personalProfileTraineePosts():
    conn = get_db_connection()
    gen_info = conn.execute('SELECT * FROM User WHERE User_ID = ?', (session["User_ID"],)).fetchone()
    trainee_info = conn.execute('SELECT * FROM Trainee WHERE Trainee_ID = ?', (session["User_ID"],)).fetchone()
    personal_posts = conn.execute('SELECT * FROM Post WHERE User_ID = ? ORDER BY Time_Stamp DESC',
                                  (session["User_ID"],)).fetchall()
    posts_comments = []
    for post in personal_posts:
        comments = conn.execute('SELECT * FROM Comment JOIN Post ON Post.Post_ID = Comment.Post_ID '
                                'JOIN User ON User.User_ID = Comment.User_ID '
                                'WHERE Post.Post_ID = ?', (post[0],)).fetchall()
        posts_comments.append(comments)
    username = conn.execute('SELECT Name FROM User WHERE User_ID = ?', (session["User_ID"],)).fetchone()
    conn.close()
    posts_with_comments = []
    for i in range(len(personal_posts)):
        post = personal_posts[i]
        if posts_comments[i]:
            comments = [
                {'Username': comment[12], 'Content': comment[3]}
                for comment in posts_comments[i]
                if comment[1] == post[0]
            ]
            posts_with_comments.append({
                'post': {
                    'pfp': serve_image("User", session["User_ID"]),
                    'Post_ID': post['Post_ID'],
                    'Content': post['Content'],
                    'Media': serve_image("Post", post['Post_ID']),
                    'Username': username[0],
                    'User_ID': post['User_ID'],
                    'Time_Stamp': post['Time_Stamp']
                },
                'comments': comments
            })
        else:
            posts_with_comments.append({
                'post': {
                    'pfp': serve_image("User", session["User_ID"]),
                    'Post_ID': post['Post_ID'],
                    'Content': post['Content'],
                    'Media': serve_image("Post", post['Post_ID']),
                    'Username': username[0],
                    'User_ID': post['User_ID'],
                    'Time_Stamp': post['Time_Stamp']
                },
                'comments': []
            })
    pfp = serve_image("User", session["User_ID"])
    return render_template("personal_profile_trainee_posts.html", posts_with_comments=posts_with_comments,
                           pfp=pfp, gen_info=gen_info, trainee_info=trainee_info)


@app.route('/profileTraineePlan', methods=['GET', 'POST'])
def personalProfileTraineePlan():
    exercising_flag = True
    conn = get_db_connection()
    pfp = serve_image("User", session["User_ID"])
    gen_info = conn.execute('SELECT * FROM User WHERE User_ID = ?', (session["User_ID"],)).fetchone()
    trainee_info = conn.execute('SELECT * FROM Trainee WHERE Trainee_ID = ?', (session["User_ID"],)).fetchone()
    plan = conn.execute('SELECT Plan FROM Plan WHERE Trainee_ID = ?', (session["User_ID"],)).fetchone()
    plan = ast.literal_eval(plan[0])
    today = datetime.now().strftime("%A")[:3]
    exercises = []
    if plan[today][0] != "Rest":
        for exercise in plan[today]:
            photo = serve_image("Exercise", str(exercise))
            ex = conn.execute('SELECT Name, Duration, Exercise_ID FROM Exercise WHERE Exercise_ID = ?',
                              (str(exercise),)).fetchall()
            exercises.append([photo, ex[0][0], ex[0][1], ex[0][2]])
    else:
        exercising_flag = False
    conn.close()
    return render_template("personal_profile_trainee_plan.html", exercises=exercises,
                           gen_info=gen_info, trainee_info=trainee_info, pfp=pfp, exercising_flag=exercising_flag)


@app.route('/saveExercise', methods=['GET', 'POST'])
def saveExercise():
    exercise_id = request.form['saveExercise']
    conn = get_db_connection()
    today_date = str(datetime.now().strftime("%Y-%m-%d"))
    no_exercise_yet = conn.execute('SELECT * FROM Trainee_Exercise WHERE Trainee_ID = ? AND Timestamp = ?',
                                   (session["User_ID"], today_date)).fetchone()
    if not no_exercise_yet:
        conn.execute('INSERT INTO Trainee_Exercise (Trainee_ID, Trainee_Exercises, Timestamp) VALUES (?, ?, ?)',
                     (session["User_ID"], exercise_id, today_date))
    else:
        prev_exercises = conn.execute('SELECT Trainee_Exercises FROM Trainee_Exercise WHERE Trainee_ID = ? '
                                      'AND Timestamp = ?', (session["User_ID"], today_date)).fetchone()
        exercises_ids = prev_exercises[0] + "," + exercise_id
        conn.execute('UPDATE Trainee_Exercise SET Trainee_Exercises = ? WHERE Trainee_ID = ? AND Timestamp = ?',
                     (exercises_ids, session["User_ID"], today_date))
    conn.commit()
    conn.close()
    return redirect(url_for("personalProfileTraineePlan"))


@app.route('/saveAllPlan', methods=['GET', 'POST'])
def saveAllPlan():
    conn = get_db_connection()
    plan = conn.execute('SELECT Plan FROM Plan WHERE Trainee_ID = ?', (session["User_ID"],)).fetchone()
    plan = ast.literal_eval(plan[0])
    today = datetime.now().strftime("%A")[:3]
    exercises_ids = ""
    if plan[today][0] != "Rest":
        for exercise in plan[today]:
            ex = conn.execute('SELECT Exercise_ID FROM Exercise WHERE Exercise_ID = ?', (str(exercise),)).fetchone()
            exercises_ids += ex[0] + ","
        exercises_ids = exercises_ids[:-1]
        today_date = str(datetime.now().strftime("%Y-%m-%d"))
        no_exercise_yet = conn.execute('SELECT * FROM Trainee_Exercise WHERE Trainee_ID = ? AND Timestamp = ?',
                                       (session["User_ID"], today_date)).fetchone()
        if not no_exercise_yet:
            conn.execute('INSERT INTO Trainee_Exercise (Trainee_ID, Trainee_Exercises, Timestamp) VALUES (?, ?, ?)',
                         (session["User_ID"], exercises_ids, today_date))
        else:
            prev_exercises = conn.execute('SELECT Trainee_Exercises FROM Trainee_Exercise WHERE Trainee_ID = ? '
                                          'AND Timestamp = ?', (session["User_ID"], today_date)).fetchone()
            exercises_ids = prev_exercises[0] + "," + exercises_ids
            conn.execute('UPDATE Trainee_Exercise SET Trainee_Exercises = ? WHERE Trainee_ID = ? AND Timestamp = ?',
                         (exercises_ids, session["User_ID"], today_date))
    conn.commit()
    conn.close()
    return redirect(url_for("personalProfileTraineePlan"))


@app.route('/profileCoachInformation', methods=['GET', 'POST'])
def personalProfileCoachInformation():
    conn = get_db_connection()
    gen_info = conn.execute('SELECT * FROM User WHERE User_ID = ?', (session["User_ID"],)).fetchone()
    coach_info = conn.execute('SELECT * FROM Coach WHERE Coach_ID = ?', (session["User_ID"],)).fetchone()
    conn.close()
    if coach_info[4]:
        certificates = coach_info[4].split(" ")
    else:
        certificates = []
    pfp = serve_image("User", session["User_ID"])
    return render_template("personal_profile_coach_information.html", gen_info=gen_info, pfp=pfp,
                           coach_info=coach_info, certificates=certificates)


@app.route('/editProfileCoach', methods=['GET', 'POST'])
def editProfileCoach():
    conn = get_db_connection()
    gen_info = conn.execute('SELECT * FROM User WHERE User_ID = ?', (session["User_ID"],)).fetchone()
    coach_info = conn.execute('SELECT * FROM Coach WHERE Coach_ID = ?', (session["User_ID"],)).fetchone()
    all_interests = conn.execute('SELECT * FROM Interest').fetchall()
    conn.close()
    if request.method == 'POST':
        pfp_file = request.files['pfp']
        username = request.form['username']
        pw = request.form['password']
        age = request.form['age']
        interests_id = request.form.getlist('interests')
        expYears = request.form['expYears']
        expDesc = request.form['expDesc']
        certificates = request.form['certificates']

        conn = get_db_connection()
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(pfp_file.read())
            temp_file_path = temp_file.name
        pfp = photo_to_binary(temp_file_path)
        os.remove(temp_file_path)
        interests = ""
        for intr in interests_id:
            inter = conn.execute('SELECT Name FROM Interest WHERE Interest_ID = ?', (intr,)).fetchone()
            interests += inter[0] + ","
        interests = interests[:-1]
        if pfp_file:
            conn.execute('UPDATE User SET Profile_picture=?, Name=?, Password=?, Age=?, Interests=? WHERE User_ID=?',
                         (pfp, username, pw, age, interests, session["User_ID"]))
        else:
            conn.execute('UPDATE User SET Name=?, Password=?, Age=?, Interests=? WHERE User_ID=?',
                         (username, pw, age, interests, session["User_ID"]))
        conn.execute('UPDATE Coach SET Description=?, Experience=?, Certificates=? WHERE Coach_ID=?',
                     (expDesc, expYears, certificates, session["User_ID"]))
        conn.commit()
        conn.close()
        return redirect(url_for("personalProfileCoachInformation"))

    return render_template("edit_profile_coach.html", gen_info=gen_info, coach_info=coach_info,
                           interests=all_interests)


@app.route('/profileCoachPosts', methods=['GET', 'POST'])
def profileCoachPosts():
    conn = get_db_connection()
    gen_info = conn.execute('SELECT * FROM User WHERE User_ID = ?', (session["User_ID"],)).fetchone()
    coach_info = conn.execute('SELECT * FROM Coach WHERE Coach_ID = ?', (session["User_ID"],)).fetchone()
    personal_posts = conn.execute('SELECT * FROM Post WHERE User_ID = ? ORDER BY Time_Stamp DESC',
                                  (session["User_ID"],)).fetchall()
    posts_comments = []
    for post in personal_posts:
        comments = conn.execute('SELECT * FROM Comment JOIN Post ON Post.Post_ID = Comment.Post_ID '
                                'JOIN User ON User.User_ID = Comment.User_ID '
                                'WHERE Post.Post_ID = ?', (post[0],)).fetchall()
        posts_comments.append(comments)
    username = conn.execute('SELECT Name FROM User WHERE User_ID = ?', (session["User_ID"],)).fetchone()
    conn.close()
    posts_with_comments = []
    for i in range(len(personal_posts)):
        post = personal_posts[i]
        if posts_comments[i]:
            comments = [
                {'Username': comment[12], 'Content': comment[3]}
                for comment in posts_comments[i]
                if comment[1] == post[0]
            ]
            posts_with_comments.append({
                'post': {
                    'pfp': serve_image("User", session["User_ID"]),
                    'Post_ID': post['Post_ID'],
                    'Content': post['Content'],
                    'Media': serve_image("Post", post['Post_ID']),
                    'Username': username[0],
                    'User_ID': post['User_ID'],
                    'Time_Stamp': post['Time_Stamp']
                },
                'comments': comments
            })
        else:
            posts_with_comments.append({
                'post': {
                    'pfp': serve_image("User", session["User_ID"]),
                    'Post_ID': post['Post_ID'],
                    'Content': post['Content'],
                    'Media': serve_image("Post", post['Post_ID']),
                    'Username': username[0],
                    'User_ID': post['User_ID'],
                    'Time_Stamp': post['Time_Stamp']
                },
                'comments': []
            })
    pfp = serve_image("User", session["User_ID"])
    return render_template("personal_profile_coach_posts.html", posts_with_comments=posts_with_comments,
                           pfp=pfp, gen_info=gen_info, coach_info=coach_info)


@app.route('/profileCoachTrainees', methods=['GET', 'POST'])
def profileCoachTrainees():
    conn = get_db_connection()
    gen_info = conn.execute('SELECT * FROM User WHERE User_ID = ?', (session["User_ID"],)).fetchone()
    coach_info = conn.execute('SELECT * FROM Coach WHERE Coach_ID = ?', (session["User_ID"],)).fetchone()
    trainees_collected = conn.execute('SELECT * FROM Trainee JOIN User '
                                      'ON User.User_ID = Trainee.Trainee_ID WHERE Coach_ID = ?',
                                      (session["User_ID"],)).fetchall()
    conn.close()
    trainees = []
    for trainee in trainees_collected:
        img = serve_image("User", trainee[0])
        trainee_info = [trainee[8], img, trainee[0]]
        trainees.append(trainee_info)
    pfp = serve_image("User", session["User_ID"])
    return render_template("personal_profile_coach_trainees.html", trainees=trainees, gen_info=gen_info,
                           coach_info=coach_info, pfp=pfp)


@app.route('/traineeStatsCoach', methods=['GET', 'POST'])
def traineeStatsCoach():
    trainee_id = request.form['trainee_id']
    conn = get_db_connection()
    trainee = True
    role = conn.execute('SELECT Role FROM User WHERE User_ID = ?', (trainee_id,)).fetchone()
    if role == "Coach":
        trainee = False
    gen_info = conn.execute('SELECT * FROM User WHERE User_ID = ?', (trainee_id,)).fetchone()
    trainee_info = conn.execute('SELECT * FROM Trainee WHERE Trainee_ID = ?', (trainee_id,)).fetchone()
    today = datetime.now().strftime("%Y-%m-%d")
    today = str(today)
    exercises_list = conn.execute('SELECT * FROM Trainee_Exercise WHERE Trainee_ID = ? AND Timestamp = ?',
                                  (trainee_id, today)).fetchall()
    workout_time = 0
    exercises = []
    if exercises_list:
        exercise_flag = True
        exercises_id = exercises_list[0][1].split(",")
        for eid in exercises_id:
            e = conn.execute('SELECT Name, Media, Duration FROM Exercise WHERE Exercise_ID = ?', (eid,)).fetchall()
            exercises.append(e[0])
        for exercise in exercises:
            workout_time += int(exercise[2])
    else:
        exercise_flag = False
    nutrition = conn.execute('SELECT * FROM Trainee_Recipes WHERE Trainee_ID = ? AND Timestamp = ?',
                             (trainee_id, today)).fetchall()
    conn.close()
    if nutrition:
        nutrition = nutrition[0]
        nutrition_flag = True
    else:
        nutrition = []
        nutrition_flag = False
    pfp = serve_image("User", trainee_id)
    workout_time = round(workout_time / 3600, 2)

    return render_template("traineeStatsCoach.html", gen_info=gen_info, pfp=pfp,
                           trainee_info=trainee_info, exercises=exercises, workout_time=workout_time,
                           nutrition=nutrition, trainee=trainee, exercise_flag=exercise_flag,
                           nutrition_flag=nutrition_flag)


@app.route('/profileCoachRecipes', methods=['GET', 'POST'])
def profileCoachRecipes():
    conn = get_db_connection()
    gen_info = conn.execute('SELECT * FROM User WHERE User_ID = ?', (session["User_ID"],)).fetchone()
    coach_info = conn.execute('SELECT * FROM Coach WHERE Coach_ID = ?', (session["User_ID"],)).fetchone()
    recipes_rows = conn.execute('SELECT * FROM Recipe WHERE Coach_ID = ?', (session["User_ID"],)).fetchall()
    conn.close()
    recipes = []
    for recipe in recipes_rows:
        recipe_img = serve_image("Recipe", recipe[0])
        #                 name        type   ingredients   steps    nutrition      img
        recipes.append([recipe[3], recipe[2], recipe[5], recipe[6], recipe[7], recipe_img])
    pfp = serve_image("User", session["User_ID"])
    return render_template("personal_profile_coach_recipes.html", recipes=recipes, gen_info=gen_info,
                           coach_info=coach_info, pfp=pfp)


@app.route('/profileCoachExercises', methods=['GET', 'POST'])
def profileCoachExercises():
    conn = get_db_connection()
    gen_info = conn.execute('SELECT * FROM User WHERE User_ID = ?', (session["User_ID"],)).fetchone()
    coach_info = conn.execute('SELECT * FROM Coach WHERE Coach_ID = ?', (session["User_ID"],)).fetchone()
    exercises_rows = conn.execute('SELECT * FROM Exercise WHERE Coach_ID = ?', (session["User_ID"],)).fetchall()
    conn.close()
    exercises = []
    for exercise in exercises_rows:
        exercise_img = serve_image("Exercise", exercise[0])
        #                   name        duration   description    muscles      equipment   more info       img
        exercises.append([exercise[2], exercise[6], exercise[7], exercise[4], exercise[5], exercise[8], exercise_img])
    pfp = serve_image("User", session["User_ID"])
    return render_template("personal_profile_coach_exercises.html", exercises=exercises, gen_info=gen_info,
                           coach_info=coach_info, pfp=pfp)


@app.route('/forgotPW', methods=['GET', 'POST'])
def forgotPW():
    if 'fp_email' not in session:
        session['fp_email'] = None
    if 'security_question' not in session:
        session["security_question"] = None
    if "show_pw_change" not in session:
        session["show_pw_change"] = False
    show_sq = False

    if request.method == 'POST':
        if (session['fp_email'] and session['security_question'] and session["show_pw_change"] is True
                and 'new_pw' in request.form):
            new_pw = request.form['new_pw']
            conn = get_db_connection()
            userid = conn.execute('SELECT User_ID FROM User WHERE Email = ?', (session["fp_email"],)).fetchone()
            conn.execute('UPDATE User SET Password = ? WHERE User_ID = ?', (new_pw, userid[0]))
            conn.commit()
            conn.close()
            session.pop('fp_email', None)
            session.pop('security_question', None)
            session.pop('show_pw_change', None)
            send_email(session["fp_email"], "Password Reset", "Your password has been reset, "
                                                              "make sure to save it this time!")
            return redirect(url_for("login"))

        elif session['fp_email']:
            if 'answer' in request.form:
                answer = request.form['answer'].lower()
                print(session["security_question"])
                if session["security_question"] and answer == session["security_question"][1].lower():
                    session["show_pw_change"] = True
                else:
                    flash("Incorrect security answer. Try again.", "error")
        elif 'email' in request.form and request.form['email']:
            email = request.form['email']
            session['fp_email'] = email
            conn = get_db_connection()
            user_sq = conn.execute('SELECT Security_Question FROM User WHERE Email = ?', (email,)).fetchone()
            conn.close()

            if user_sq:
                session["security_question"] = user_sq[0].split(",")
                show_sq = True
            else:
                flash("Invalid email. Try again.", "error")
                session['fp_email'] = None
                session['security_question'] = None

    if session['fp_email'] and session["security_question"]:
        show_sq = True
    return render_template(
        "forgotPW.html", show_sq=show_sq,
        security_question=session["security_question"][0] if session["security_question"]
        else "", show_pw_change=session["show_pw_change"])


# user redirection per user role
@app.route('/redirect', methods=['GET', 'POST'])
def redirectPerRole():
    User_ID = str(session['User_ID'])
    conn = get_db_connection()
    # save logged in user's role
    role = conn.execute('SELECT Role FROM User WHERE User_ID = ?', (User_ID,)).fetchone()
    conn.close()
    role = role[0]
    # direct to admin's page
    if role == "Admin":
        return redirect(url_for('unverifiedCoaches'))
    elif role == "Coach":
        conn = get_db_connection()
        verification = conn.execute('SELECT Verified FROM Coach WHERE Coach_ID = ?', (User_ID,)).fetchone()
        verification = verification[0]
        conn.close()
        # if a coach is verified direct to homepage
        if verification == "TRUE":
            return redirect(url_for('posts'))
        session.pop('User_ID', None)
        return render_template("await_verification.html")
    return redirect(url_for('posts'))


# log out users
@app.route('/logout', methods=['GET', 'POST'])
def logout():
    # remove the saved userid
    session.pop('User_ID', None)
    # inform the user they logged out
    flash('You have been logged out.', 'info')
    # redirect to login page
    return redirect(url_for('login'))


@app.route('/google/')
def google():
    nonce = os.urandom(16).hex()
    session['oauth_nonce'] = nonce
    redirect_uri = url_for('google_auth', _external=True)
    return oauth.google.authorize_redirect(redirect_uri, nonce=nonce, prompt="select_account")


@app.route('/google/auth/')
def google_auth():
    token = oauth.google.authorize_access_token()

    nonce = session.pop('oauth_nonce', None)
    if nonce is None:
        return redirect(url_for('google'))

    user = oauth.google.parse_id_token(token, nonce=nonce)
    auth = user.get("sub")
    conn = get_db_connection()
    a_user = conn.execute('SELECT * FROM User WHERE Authentication = ?', (str(auth),)).fetchone()
    if a_user:
        session['User_ID'] = a_user[0]
        return redirect(url_for('redirectPerRole'))
    session["auth"] = auth
    session["oauth_email"] = user.get("email")
    if session["role"] == "Trainee":
        return redirect(url_for("oauthTraineeSignup"))
    return redirect(url_for("oauthCoachSignup"))


@app.route('/oauthTraineeSignup', methods=['GET', 'POST'])
def oauthTraineeSignup():
    questions = ["What was your dream job as a child?", "What was the name of your first stuffed animal?",
                 "What was the color of your favorite childhood blanket?"]
    security_question = questions[np.random.randint(0, len(questions))]
    # save the trainee's information based on their input
    if request.method == 'POST':
        role = "Trainee"
        username = request.form['username']
        age = request.form['age']
        weight = request.form['weight']
        height = request.form['height']
        gender = request.form['gender']
        exercise = request.form['exercise']
        bmi = round(float(weight) / (float(height) ** 2), 2)
        interests_id = request.form.getlist('interests')
        security_answer = request.form['sec_ans']

        conn = get_db_connection()
        # save interests entered by their names
        interests = ""
        for intr in interests_id:
            inter = conn.execute('SELECT Name FROM Interest WHERE Interest_ID = ?', (intr,)).fetchone()
            interests += inter[0] + ","
        interests = interests[:-1]
        # calculate new userid
        userid_count = conn.execute('SELECT COUNT(*) FROM User').fetchone()
        userid = str(userid_count[0] + 1)
        sec_qa = security_question + "," + security_answer
        # add trainee to user table
        conn.execute('INSERT INTO User (User_ID, Name, Age, Gender, Authentication, '
                     'Role, Interests, Security_Question) '
                     'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                     (userid, username, age, gender, session["auth"], role, interests, sec_qa))

        # add trainee to trainee table
        conn.execute('INSERT INTO Trainee (Trainee_ID, Weight_kg, Height_m, BMI, Exercise_Level) '
                     'VALUES (?, ?, ?, ?, ?)',
                     (userid, weight, height, str(bmi), exercise))

        # calculate new planid
        planid_count = conn.execute('SELECT COUNT(*) FROM Plan').fetchone()
        planid = str(planid_count[0] + 1)

        # add basic plan based on gender
        if gender == "Female":
            init_plan = conn.execute('SELECT Plan FROM Plan WHERE Trainee_ID = ?', ("2",)).fetchone()
            conn.execute('INSERT INTO Plan (Plan_ID, Trainee_ID, Plan) VALUES (?, ?, ?)',
                         (planid, userid, init_plan[0]))
        else:
            init_plan = conn.execute('SELECT Plan FROM Plan WHERE Trainee_ID = ?', ("38",)).fetchone()
            print(init_plan)
            conn.execute('INSERT INTO Plan (Plan_ID, Trainee_ID, Plan) VALUES (?, ?, ?)',
                         (planid, userid, init_plan[0]))
        conn.commit()
        conn.close()
        session["auth"] = None
        # return user to login page
        return redirect(url_for('login'))
    conn = get_db_connection()
    all_interests = conn.execute('SELECT * FROM Interest').fetchall()
    conn.close()
    return render_template("oauthTraineeSignup.html", security_question=security_question, interests=all_interests)


# trainee sign-up
@app.route('/trainee', methods=["GET", "POST"])
def traineeSignUp():
    email_exists = False
    questions = ["What was your dream job as a child?", "What was the name of your first stuffed animal?",
                 "What was the color of your favorite childhood blanket?"]
    security_question = questions[np.random.randint(0, len(questions))]
    # save the trainee's information based on their input
    if request.method == 'POST':
        role = "Trainee"
        username = request.form['username']
        email = request.form['email']
        age = request.form['age']
        weight = request.form['weight']
        height = request.form['height']
        gender = request.form['gender']
        exercise = request.form['exercise']
        password = request.form['password']
        bmi = round(int(weight) / (float(height) ** 2), 2)
        interests_id = request.form.getlist('interests')
        security_answer = request.form['sec_ans']

        conn = get_db_connection()
        # save interests entered by their names
        interests = ""
        for intr in interests_id:
            inter = conn.execute('SELECT Name FROM Interest WHERE Interest_ID = ?', (intr,)).fetchone()
            interests += inter[0] + ","
        interests = interests[:-1]
        # calculate new userid
        userid_count = conn.execute('SELECT COUNT(*) FROM User').fetchone()
        userid = str(userid_count[0] + 1)

        # check if email already used for another user
        email_check = conn.execute('SELECT * FROM User WHERE Email = ?', (email,)).fetchone()
        if not email_check:
            sec_qa = security_question + "," + security_answer
            hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
            # add trainee to user table
            conn.execute('INSERT INTO User (User_ID, Name, Email, Age, Gender, Password, '
                         'Role, Interests, Security_Question) '
                         'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                         (userid, username, email, age, gender, hashed_password, role, interests, sec_qa))

            # add trainee to trainee table
            conn.execute('INSERT INTO Trainee (Trainee_ID, Weight_kg, Height_m, BMI, Exercise_Level) '
                         'VALUES (?, ?, ?, ?, ?)',
                         (userid, weight, height, bmi, exercise))

            # calculate new planid
            planid_count = conn.execute('SELECT COUNT(*) FROM Plan').fetchone()
            planid = str(planid_count[0] + 1)

            # add basic plan based on gender
            if gender == "Female":
                init_plan = conn.execute('SELECT Plan FROM Plan WHERE Trainee_ID = ?', ("2",)).fetchone()
                conn.execute('INSERT INTO Plan (Plan_ID, Trainee_ID, Plan) VALUES (?, ?, ?)',
                             (planid, userid, init_plan[0]))
            else:
                init_plan = conn.execute('SELECT Plan FROM Plan WHERE Trainee_ID = ?', ("38",)).fetchone()
                print(init_plan)
                conn.execute('INSERT INTO Plan (Plan_ID, Trainee_ID, Plan) VALUES (?, ?, ?)',
                             (planid, userid, init_plan[0]))
            conn.commit()
            conn.close()
            # return user to login page
            return redirect(url_for('login'))
        email_exists = True
    # get all interests from database to show in form
    conn = get_db_connection()
    all_interests = conn.execute('SELECT * FROM Interest').fetchall()
    conn.close()
    return render_template("traineeSignUp.html", interests=all_interests, email_exists=email_exists,
                           security_question=security_question)


# coach sign-up
@app.route('/coach', methods=["GET", "POST"])
def coachSignUp():
    email_exists = False
    questions = ["What was your dream job as a child?", "What was the name of your first stuffed animal?",
                 "What was the color of your favorite childhood blanket?"]
    security_question = questions[np.random.randint(0, len(questions))]
    # save the coach's information based on their input
    if request.method == 'POST':
        role = "Coach"
        verified = "FALSE"
        username = request.form['username']
        email = request.form['email']
        age = request.form['age']
        expYears = str(request.form['expYears']) + " years"
        expDesc = request.form['expDesc']
        gender = request.form['gender']
        certificates = request.form['certificates']
        password = request.form['password']
        interests_id = request.form.getlist('interests')
        security_answer = request.form['sec_ans']

        conn = get_db_connection()
        # save interests entered by their names
        interests = ""
        for intr in interests_id:
            inter = conn.execute('SELECT Name FROM Interest WHERE Interest_ID = ?', (intr,)).fetchone()
            interests += inter[0] + ","
        interests = interests[:-1]
        # calculate new userid
        userid_count = conn.execute('SELECT COUNT(*) FROM User').fetchone()
        userid = str(userid_count[0] + 1)

        # check if email already used for another user
        email_check = conn.execute('SELECT * FROM User WHERE Email = ?', (email,)).fetchone()
        if not email_check:
            sec_qa = security_question + "," + security_answer
            hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
            # add coach to user table
            conn.execute('INSERT INTO User (User_ID, Name, Email, Age, Gender, Password, '
                         'Role, Interests, Security_Question) '
                         'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                         (userid, username, email, age, gender, hashed_password, role, interests, sec_qa))

            # add coach to coach table
            conn.execute('INSERT INTO Coach (Coach_ID, Verified, Description, Experience, Certificates) '
                         'VALUES (?, ?, ?, ?, ?)',
                         (userid, verified, expDesc, expYears, certificates))

            conn.commit()
            conn.close()
            # return user to login page
            return redirect(url_for('login'))
        email_exists = True
    # get all interests from database to show in form
    conn = get_db_connection()
    all_interests = conn.execute('SELECT * FROM Interest').fetchall()
    conn.close()
    return render_template("coachSignUp.html", interests=all_interests, email_exists=email_exists,
                           security_question=security_question)


@app.route('/oauthCoachSignup', methods=['GET', 'POST'])
def oauthCoachSignup():
    questions = ["What was your dream job as a child?", "What was the name of your first stuffed animal?",
                 "What was the color of your favorite childhood blanket?"]
    security_question = questions[np.random.randint(0, len(questions))]
    # save the coach's information based on their input
    if request.method == 'POST':
        role = "Coach"
        verified = "FALSE"
        username = request.form['username']
        age = request.form['age']
        expYears = str(request.form['expYears']) + " years"
        expDesc = request.form['expDesc']
        gender = request.form['gender']
        certificates = request.form['certificates']
        interests_id = request.form.getlist('interests')
        security_answer = request.form['sec_ans']

        conn = get_db_connection()
        # save interests entered by their names
        interests = ""
        for intr in interests_id:
            inter = conn.execute('SELECT Name FROM Interest WHERE Interest_ID = ?', (intr,)).fetchone()
            interests += inter[0] + ","
        interests = interests[:-1]
        # calculate new userid
        userid_count = conn.execute('SELECT COUNT(*) FROM User').fetchone()
        userid = str(userid_count[0] + 1)

        sec_qa = security_question + "," + security_answer
        # add coach to user table
        conn.execute('INSERT INTO User (User_ID, Name, Age, Gender, Email, '
                     'Role, Interests, Security_Question, Authentication) '
                     'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                     (userid, username, age, gender, session["oauth_email"], role, interests, sec_qa, session["auth"]))
        session["oauth_email"] = None
        # add coach to coach table
        conn.execute('INSERT INTO Coach (Coach_ID, Verified, Description, Experience, Certificates) '
                     'VALUES (?, ?, ?, ?, ?)',
                     (userid, verified, expDesc, expYears, certificates))

        conn.commit()
        conn.close()
        # return user to login page
        return redirect(url_for('login'))
    # get all interests from database to show in form
    conn = get_db_connection()
    all_interests = conn.execute('SELECT * FROM Interest').fetchall()
    conn.close()
    return render_template("oauthCoachSignUp.html", interests=all_interests, security_question=security_question)


# admin page
@app.route('/admin', methods=["GET", "POST"])
def unverifiedCoaches():
    conn = get_db_connection()
    # get all unverified coaches
    unverified_Coaches = conn.execute('SELECT * FROM Coach JOIN User ON User_ID=Coach_ID '
                                      'WHERE Verified = "FALSE"').fetchall()
    certificates = {}
    for coach in unverified_Coaches:
        if coach[4]:
            certificates[coach[0]] = (coach[4].split(" "))
        else:
            certificates[coach[0]] = []
    conn.close()
    return render_template("verifyCoaches.html", coaches=unverified_Coaches, certificates=certificates)


# logic for coach verification
@app.route('/verify_coach', methods=["GET", "POST"])
def verifyCoach():
    # gets coachID
    coachID = request.form['verify_coach']
    conn = get_db_connection()
    # updates coach status to verified
    coach_mail = conn.execute('SELECT Email From User WHERE User_ID=?', (coachID,)).fetchone()[0]
    conn.execute('UPDATE Coach SET Verified = "TRUE" WHERE Coach_ID=?', (coachID,))
    conn.commit()
    conn.close()
    send_email(coach_mail, "FitHub Access",
               "Congratulation! You got verified, you can now access our site as a coach :D")
    # return to admin page
    return redirect(url_for('unverifiedCoaches'))


# logic for coach denial
@app.route('/deny_coach', methods=["GET", "POST"])
def denyCoach():
    # gets coachID
    coachID = request.form['deny_coach']
    conn = get_db_connection()
    coach_mail = conn.execute('SELECT Email From User WHERE User_ID=?', (coachID,)).fetchone()[0]
    # delete coach from coach & user tables
    conn.execute('DELETE FROM Coach WHERE Coach_ID=?', (coachID,))
    conn.execute('DELETE FROM User WHERE User_ID=?', (coachID,))
    conn.commit()
    conn.close()
    send_email(coach_mail, "FitHub Access", "Unfortunately, you have been denied access to FitHub. "
                                            "Work on your experiences and try again!")
    # return to admin page
    return redirect(url_for('unverifiedCoaches'))


# function to get user information
def get_user(User_ID):
    conn = get_db_connection()  # connect to database
    user = conn.execute('SELECT * FROM User WHERE User_ID = ?', (User_ID,)).fetchone()  # fetch user info
    return user, conn


# function to get all interests
def get_interests(conn):
    return conn.execute('SELECT * FROM Interest').fetchall()  # fetch all interests


# function to handle post submission
def share_post(conn, post_content, post_media, selected_tags, user):
    postid_count = conn.execute('SELECT COUNT(*) FROM Post').fetchone()
    postid = postid_count[0] + 1
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    tags_str = '/'.join(selected_tags)

    # save media as a temporary file and convert it to binary data
    media_data = None
    if post_media:
        # save the file to a temporary location
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(post_media.read())
            temp_file_path = temp_file.name

        # convert the temporary file to binary data
        media_data = photo_to_binary(temp_file_path)

        # clean up the temporary file
        os.remove(temp_file_path)

    conn.execute(
        '''INSERT INTO Post (Post_ID, User_ID, Content, Time_Stamp, Media, Tags) 
           VALUES (?, ?, ?, ?, ?, ?)''',
        (postid, user['User_ID'], post_content, current_time, media_data, tags_str)
    )
    conn.commit()


# function to get user interests
def get_user_interests(user):
    return user['Interests'].split(',') if user['Interests'] else []


# function to fetch posts by interest
def fetch_posts_by_interest(conn, user_interests):
    if user_interests:
        placeholders = ', '.join(['?'] * len(user_interests))  # placeholders for query
        return conn.execute(
            f'''SELECT Post.*, User.Name AS Username 
                FROM Post 
                JOIN User ON Post.User_ID = User.User_ID
                WHERE EXISTS (
                    SELECT 1 FROM Interest 
                    WHERE Interest.Name IN ({placeholders}) 
                      AND Post.Tags LIKE '%' || Interest.Interest_ID || '%'
                )
                ORDER BY Post.Time_Stamp DESC''',
            tuple(user_interests)
        ).fetchall()
    return []


# function to fetch remaining posts
def fetch_remaining_posts(conn, user_interests):
    if user_interests:
        return conn.execute(
            '''SELECT Post.*, User.Name AS Username 
               FROM Post 
               JOIN User ON Post.User_ID = User.User_ID
               WHERE Post.Post_ID NOT IN (
                   SELECT Post.Post_ID 
                   FROM Post 
                   JOIN Interest 
                   ON Post.Tags LIKE '%' || Interest.Interest_ID || '%'
                   WHERE Interest.Name IN ({}))
               ORDER BY Post.Time_Stamp DESC'''.format(', '.join(['?'] * len(user_interests))),
            tuple(user_interests)
        ).fetchall()
    return conn.execute(
        '''SELECT Post.*, User.Name AS Username 
           FROM Post 
           JOIN User ON Post.User_ID = User.User_ID
           ORDER BY Post.Time_Stamp DESC'''
    ).fetchall()


# function to fetch comments with usernames
def fetch_comments_with_usernames(conn):
    return conn.execute('''SELECT Comment.*, User.Name AS Username 
                           FROM Comment 
                           JOIN User ON Comment.User_ID = User.User_ID''').fetchall()


# function to combine posts with their respective comments
def combine_posts_and_comments(all_posts, comments_with_usernames):
    posts_with_comments = []
    for post in all_posts:
        post_comments = [
            {'Username': comment['Username'], 'Content': comment['Content']}
            for comment in comments_with_usernames
            if comment['Post_ID'] == post['Post_ID']
        ]
        photo = serve_image("Post", post['Post_ID'])
        img = serve_image("User", post['User_ID'])
        posts_with_comments.append({
            'post': {
                'Post_ID': post['Post_ID'],
                'Content': post['Content'],
                'Media': photo,
                'Username': post['Username'],
                'User_ID': post['User_ID'],
                'Time_Stamp': post['Time_Stamp'],
                'pfp': img
            },
            'comments': post_comments
        })
    return posts_with_comments


# route to display and create posts
@app.route('/posts', methods=['GET', 'POST'])
def posts():
    # check if a user is logged in
    if 'User_ID' in session:
        User_ID = session['User_ID']  # get user id from session

        # Get user info and interests
        user, conn = get_user(User_ID)
        all_interests = get_interests(conn)

        # handle post submission
        if request.method == 'POST':
            post_content = request.form['content']  # get post content
            post_media = request.files['media']  # get post media (to be handled)
            selected_tags = request.form.getlist('tags')  # get selected tags as a list
            share_post(conn, post_content, post_media, selected_tags, user)

        # get user interests and posts
        user_interests = get_user_interests(user)
        posts_by_interest = fetch_posts_by_interest(conn, user_interests)
        remaining_posts = fetch_remaining_posts(conn, user_interests)

        # combine and sort all posts by timestamp
        all_posts = sorted(posts_by_interest + remaining_posts, key=lambda x: x['Time_Stamp'], reverse=True)

        # fetch all comments with usernames
        comments_with_usernames = fetch_comments_with_usernames(conn)

        # combine posts with their respective comments
        posts_with_comments = combine_posts_and_comments(all_posts, comments_with_usernames)

        conn.close()  # close database connection
        # render posts page with user, posts, and interests
        return render_template("posts.html", user=user, posts_with_comments=posts_with_comments, interests=all_interests)

    # redirect to login page if no user is logged in
    return redirect(url_for('login'))


# route to add a comment to a post
@app.route('/add_comment/<int:post_id>', methods=['POST'])
def add_comment(post_id):
    # check if a user is logged in
    if 'User_ID' in session:
        User_ID = session['User_ID']  # get user id from session
        conn = get_db_connection()  # connect to database

        # calculate new comment id
        commentid_count = conn.execute('SELECT COUNT(*) FROM Comment').fetchone()
        commentid = commentid_count[0] + 1  # increment comment count for unique id

        # get comment content from form
        comment_content = request.form['comment_content']

        # get current datetime in standardized format
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M")

        # save comment to database
        conn.execute(
            'INSERT INTO Comment (Comment_ID, Post_ID, User_ID, Content, Time_Stamp) VALUES (?, ?, ?, ?, ?)',
            (commentid, post_id, User_ID, comment_content, current_time)
        )
        conn.commit()  # commit changes to database
        conn.close()  # close database connection

        # redirect back to posts page
        return redirect(url_for('posts'))

    # redirect to login page if no user is logged in
    return redirect(url_for('login'))


# route to display chats for current user or specific chat
@app.route('/chats', methods=['GET', 'POST'])
def view_chats():
    # redirect to login if not logged in
    if 'User_ID' not in session:
        return redirect(url_for('login'))

    # get current user ID from session
    current_user_id = session['User_ID']

    # connect to database
    conn = get_db_connection()

    # fetch chats for current user
    chats = conn.execute('''
        SELECT Chat.Chat_ID,
               CASE
                   WHEN Chat.User1_ID = ? THEN Chat.User2_ID
                   ELSE Chat.User1_ID
               END AS Other_User_ID,
               (SELECT Name FROM User WHERE User.User_ID =
                   CASE
                       WHEN Chat.User1_ID = ? THEN Chat.User2_ID
                       ELSE Chat.User1_ID
                   END) AS Other_User_Name
        FROM Chat
        WHERE Chat.User1_ID = ? OR Chat.User2_ID = ?
        ORDER BY (SELECT MAX(Time_Stamp) FROM Message WHERE Message.Chat_ID = Chat.Chat_ID) DESC
    ''', (current_user_id, current_user_id, current_user_id, current_user_id)).fetchall()

    # get selected chat ID from URL
    selected_chat_id = request.args.get('chat_id')
    selected_chat = None
    messages = []

    # if chat selected, fetch messages
    if selected_chat_id:
        selected_chat = next((chat for chat in chats if str(chat['Chat_ID']) == selected_chat_id), None)
        if selected_chat:
            # fetch messages for selected chat
            messages = conn.execute('''
                SELECT Message.Content, Message.Sender_ID, Message.Time_Stamp, User.Name
                FROM Message
                JOIN User ON Message.Sender_ID = User.User_ID
                WHERE Message.Chat_ID = ?
                ORDER BY Message.Time_Stamp ASC
            ''', (selected_chat_id,)).fetchall()
        else:
            # show error if chat invalid
            flash('Invalid chat selected.', 'danger')

    # close database connection
    conn.close()

    # render chat page
    return render_template('chat.html', chats=chats, selected_chat=selected_chat, messages=messages,
                           current_user_id=current_user_id)


# route to handle sending new message
@app.route('/send_message', methods=['POST'])
def send_message():
    # redirect to login if not logged in
    if 'User_ID' not in session:
        return redirect(url_for('login'))

    # get current user ID from session
    current_user_id = session['User_ID']

    # get chat ID and message content from form
    chat_id = request.form.get('chat_id')
    message_content = request.form.get('message_content')

    # log chat ID and message content for debugging
    print(f"Chat ID: {chat_id}, Message Content: {message_content}")

    # show error if chat ID or message content missing
    if not chat_id or not message_content:
        flash('Chat ID and message content are required.', 'error')
        return redirect(url_for('view_chats', chat_id=chat_id))

    conn = get_db_connection()
    try:
        # calculate new message ID
        messegeid_count = conn.execute('SELECT COUNT(*) FROM Message').fetchone()
        new_message_id = messegeid_count[0] + 1

        # insert message into database
        conn.execute('''
            INSERT INTO Message (Message_ID, Chat_ID, Sender_ID, Content, Time_Stamp)
            VALUES (? ,?, ?, ?, datetime('now'))
        ''', (new_message_id, chat_id, current_user_id, message_content))

        # commit changes and close connection
        conn.commit()
        conn.close()

        # show success message
        flash('Message sent successfully!', 'success')
    except Exception as e:
        # rollback on error and close connection
        conn.rollback()
        conn.close()

        # show error message
        flash(f'Failed to send message: {str(e)}', 'error')

    # redirect to chat view page
    return redirect(url_for('view_chats', chat_id=chat_id))


# Coach can add new recipes
@app.route('/add_recipe', methods=['GET', 'POST'])
def add_recipe():
    if 'User_ID' not in session:
        return redirect(url_for('login'))

    User_ID = str(session['User_ID'])

    if request.method == 'POST':
        # Get form data
        recipe_name = request.form.get('Recipe_Name')
        meal_type = request.form.get('Meal_Type')
        nutrition_info = request.form.get('Nutrition_Information')
        media = request.files.get('Media')
        steps = request.form.get('Steps')
        ingredients = request.form.get('Ingredients')
        if not (recipe_name and meal_type and nutrition_info and media and steps and ingredients):
            flash("All fields are required!", 'error')
            return redirect(url_for('add_recipe'))

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Generate a new Recipe_ID
            cursor.execute("SELECT MAX(CAST(Recipe_ID AS INTEGER)) FROM Recipe")
            max_id = cursor.fetchone()[0]
            new_recipe_id = str((max_id + 1) if max_id is not None else 1)  # Handle case where table is empty
            print(f"Generated new Recipe_ID: {new_recipe_id}")
            temp_path = f"uploads/{media.filename}"
            media.save(temp_path)

            # Upload media file and get its unique identifier
            drive_file_id = upload(temp_path, media.filename)
            if not drive_file_id:
                os.remove(temp_path)
                flash("Failed to upload media file. Please try again.", 'error')
                return redirect(url_for('add_recipe'))

            os.remove(temp_path)
            print(f"Uploaded media file ID: {drive_file_id}")

            # Insert the new recipe details into the database
            cursor.execute("""
                INSERT INTO Recipe (Recipe_ID, Coach_ID, Recipe_Name, Meal_Type,
                Nutrition_Information, Media, Steps, Ingredients)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (new_recipe_id, User_ID, recipe_name, meal_type, nutrition_info, drive_file_id, steps, ingredients))

            conn.commit()
            conn.close()

            print(f"New Recipe added successfully with ID: {new_recipe_id}")
            flash(f"Recipe added successfully with ID: {new_recipe_id}!", 'success')
            return redirect(url_for('GetRecipes'))

        except Exception as e:
            print(f"Error occurred while adding recipe: {str(e)}")
            flash(f"An error occurred: {str(e)}. Please try again later.", 'error')
            return redirect(url_for('add_recipe'))

    return render_template('add_recipe.html')


# Show all recipes to user
@app.route('/recipes', methods=['GET'])
def GetRecipes():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Recipe")
    recipes = cursor.fetchall()

    recipes_data = [{
        'Recipe_ID': str(row[0]),
        'Recipe_Name': row[3],
        'Meal_Type': row[2],
        'Media': row[4],
        'Ingredients': row[5],
        'Steps': row[6],
        'Nutrition_Information': row[7]
    } for row in recipes]

    return render_template('recipes.html', recipes=recipes_data)


# Show recipes details when the user click on more details
@app.route('/recipes/<recipe_id>', methods=['GET'])
def GetRecipeDetails(recipe_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM Recipe WHERE Recipe_ID = ?", (recipe_id,))
    recipe = cursor.fetchone()

    if recipe is None:
        return "Recipe not found", 404

    recipe_data = {
        'Recipe_ID': str(recipe[0]),
        'Recipe_Name': recipe[3],
        'Meal_Type': recipe[2],
        'Media': recipe[4],
        'Ingredients': recipe[5],
        'Steps': recipe[6],
        'Nutrition_Information': recipe[7]
    }

    return render_template('recipes_detailed.html', recipe=recipe_data)


# Show coach details for trainee so that he can add the suitable coach for him
@app.route('/coaches', methods=['GET'])
def GetCoach():
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
    SELECT  Coach_ID, Verified, Description, Experience, Certificates
    FROM Coach
    """
    cursor.execute(query)
    result = cursor.fetchall()
    coaches_data = [
        {"Coach_ID": row[0], "Verified": row[1], "Description": row[2], "Experience": row[3], "Certificates": row[4],
         } for row in result]

    return render_template('coaches_details.html', coaches=coaches_data)


# show exercises for users
@app.route('/exercises', methods=['GET'])
def GetExercises():
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT Exercise_ID, Name, Media, Duration, Equipment, Muscles_Targeted FROM Exercise")

        exercises = cursor.fetchall()
        conn.close()

        # Convert binary media to Base64 string
        exercises_data = []
        for exercise in exercises:
            media_base64 = None
            if exercise["Media"]:
                media_base64 = base64.b64encode(exercise["Media"]).decode('utf-8')
                media_base64 = f"data:image/jpeg;base64,{media_base64}"  # Assuming JPEG format

            exercises_data.append({
                "Exercise_ID": exercise["Exercise_ID"],
                "Name": exercise["Name"],
                "Media": media_base64,
                "Duration": exercise["Duration"],
                "Equipment": exercise["Equipment"],
                "Muscles_Targeted": exercise["Muscles_Targeted"]
            })

        return render_template('exercises.html', Exercises=exercises_data)
    except Exception as e:
        print(f"Error fetching exercises: {e}")
        return "Error fetching exercises", 500


# Show more details for user about the clicked exercises
@app.route('/exercise/<int:exercise_id>', methods=['GET'])
def GetExerciseDetails(exercise_id):
    import base64

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = """
        SELECT Exercise_ID, Coach_ID, Name, Media, Duration, Description, Equipment, Muscles_Targeted
        FROM Exercise
        WHERE CAST(Exercise_ID AS TEXT) = ?
    """
    cursor.execute(query, (str(exercise_id),))
    result = cursor.fetchone()

    if result:
        media_base64 = None
        if result["Media"]:
            media_base64 = base64.b64encode(result["Media"]).decode('utf-8')
            media_base64 = f"data:image/jpeg;base64,{media_base64}"  # Assuming JPEG format
            print("Base64 Encoded Media:", media_base64[:100])  # Log the first 100 chars of the Base64 string

        exercise_details = {
            "Exercise_ID": result["Exercise_ID"],
            "Coach_ID": result["Coach_ID"],
            "Name": result["Name"],
            "Media": media_base64,
            "Duration": result["Duration"],
            "Description": result["Description"],
            "Equipment": result["Equipment"],
            "Muscles_Targeted": result["Muscles_Targeted"]
        }
        return render_template('exercises_detailed.html', exercise=exercise_details)
    else:
        return "Exercise not found", 404


# Coach can add new exercises
@app.route('/add_exercises', methods=['GET', 'POST'])
def AddExercises():
    if 'User_ID' not in session:
        return redirect(url_for('login'))

    User_ID = str(session['User_ID'])

    if request.method == 'POST':
        # Get form data
        name = request.form.get('Name')
        media = request.files.get('Media')
        duration = request.form.get('Duration')
        equipment = request.form.get('Equipment')
        description = request.form.get('Description')
        muscles_targeted = request.form.get('Muscles_Targeted')

        # Validate form data
        if not (name and media and duration and equipment and description and muscles_targeted):
            flash("All fields are required!", 'error')
            return redirect(url_for('AddExercises'))

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Generate a new random exercise ID
            random_exercise_id = random.randint(1000, 9999)
            cursor.execute("SELECT 1 FROM Exercise WHERE Exercise_ID = ?", (random_exercise_id,))
            while cursor.fetchone():
                random_exercise_id = random.randint(1000, 9999)
            print(f"Generated Exercise ID: {random_exercise_id}")
            temp_path = f"uploads/{media.filename}"
            media.save(temp_path)

            drive_file_id = upload(temp_path, media.filename)
            if not drive_file_id:
                os.remove(temp_path)  # Clean up temporary file if upload failed
                flash("Failed to upload media file. Please try again.", 'error')
                return redirect(url_for('AddExercises'))
            # Clean up the temporary file
            os.remove(temp_path)
            print(f"Uploaded media file ID: {drive_file_id}")
            # Insert the exercise details into the database
            cursor.execute("""
                INSERT INTO Exercise (Exercise_ID, Coach_ID, Name, Media,
                Duration, Equipment, Description, Muscles_Targeted)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (random_exercise_id, User_ID, name, drive_file_id, duration, equipment, description, muscles_targeted))

            conn.commit()
            conn.close()

            print(f"Exercise added successfully with ID: {random_exercise_id}!")
            flash(f"Exercise added successfully with ID: {random_exercise_id}!", 'success')
            return redirect(url_for('GetExerciseDetails', exercise_id=random_exercise_id))

        except Exception as e:
            print(f"Error occurred while adding exercise: {str(e)}")
            flash(f"An error occurred: {str(e)}. Please try again later.", 'error')
            return redirect(url_for('AddExercises'))
    return render_template('add_exercise.html')


@app.route('/add_recipe_to_trainee', methods=['POST'])
def add_recipe_to_trainee():
    if 'User_ID' not in session:
        flash("You need to be logged in to perform this action.", "danger")
        return redirect(url_for('login'))
    user_id = session['User_ID']
    recipe_id = request.form.get('recipe_id')
    conn = get_db_connection()

    try:
        # Verify if the user is a trainee
        trainee = conn.execute('SELECT * FROM Trainee WHERE Trainee_ID = ?', (user_id,)).fetchone()
        if not trainee:
            flash("You are not authorized to add recipes.", "danger")
            return redirect(url_for('GetRecipes'))

        # Fetch recipe's nutritional information
        recipe = conn.execute('SELECT Nutrition_Information FROM Recipe WHERE Recipe_ID = ?', (recipe_id,)).fetchone()
        if not recipe:
            flash("Recipe not found.", "danger")
            return redirect(url_for('GetRecipes'))

        # Parse nutritional information
        nutrition_parts = {
            item.split(':')[0].strip(): float(item.split(':')[1].strip().replace('g', '').strip())
            for item in recipe['Nutrition_Information'].split(',')
        }

        calories = nutrition_parts.get('Calories', 0)
        fats = nutrition_parts.get('Fat', 0)
        carbs = nutrition_parts.get('Carbs', 0)
        protein = nutrition_parts.get('Protein', 0)

        # Get today's date (without the time)
        today_date = datetime.now().strftime("%Y-%m-%d")

        # Check if an entry already exists for the trainee for today's date in Trainee_Recipes
        existing_entry = conn.execute("""
            SELECT
                IFNULL(Trainee_Calories, 0) AS Trainee_Calories,
                IFNULL(Trainee_Fat, 0) AS Trainee_Fat,
                IFNULL(Trainee_Carbs, 0) AS Trainee_Carbs,
                IFNULL(Trainee_Protein, 0) AS Trainee_Protein
            FROM Trainee_Recipes
            WHERE Trainee_ID = ? AND DATE(Timestamp) = ?
        """, (user_id, today_date)).fetchone()

        if existing_entry:
            # Sum the existing values with the new ones
            updated_calories = existing_entry['Trainee_Calories'] + calories
            updated_fats = existing_entry['Trainee_Fat'] + fats
            updated_carbs = existing_entry['Trainee_Carbs'] + carbs
            updated_protein = existing_entry['Trainee_Protein'] + protein

            # Update the record for today's date
            conn.execute("""
                UPDATE Trainee_Recipes
                SET Trainee_Calories = ?, Trainee_Fat = ?, Trainee_Carbs = ?, Trainee_Protein = ?
                WHERE Trainee_ID = ? AND DATE(Timestamp) = ?
            """, (updated_calories, updated_fats, updated_carbs, updated_protein, user_id, today_date))
        else:
            # Insert a new record for today's date
            conn.execute("""
                INSERT INTO Trainee_Recipes (Trainee_ID, Timestamp, Trainee_Calories, Trainee_Fat,
                Trainee_Carbs, Trainee_Protein)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, today_date, calories, fats, carbs, protein))

        conn.commit()
        flash("Recipe added to your daily totals successfully!", "success")
    except Exception as e:
        flash(f"An error occurred: {str(e)}", "danger")
    finally:
        conn.close()

    return redirect(url_for('GetRecipeDetails', recipe_id=recipe_id))


@app.route('/add_exercise_to_trainee', methods=['POST'])
def add_exercise_to_trainee():
    if 'User_ID' not in session:
        flash("You need to be logged in to perform this action.", "danger")
        return redirect(url_for('login'))

    user_id = session['User_ID']
    exercise_id = request.form.get('exercise_id')

    conn = get_db_connection()

    try:
        # Verify the user is a trainee
        trainee = conn.execute('SELECT * FROM Trainee WHERE Trainee_ID = ?', (user_id,)).fetchone()
        if not trainee:
            flash("You are not authorized to add exercises.", "danger")
            return redirect(url_for('GetExercises'))

        # Verify the exercise exists
        exercise = conn.execute('SELECT * FROM Exercise WHERE Exercise_ID = ?', (exercise_id,)).fetchone()
        if not exercise:
            flash("Exercise not found.", "danger")
            return redirect(url_for('GetExercises'))

        today_date = datetime.now().strftime("%Y-%m-%d")

        # Check if the exercise already exists for the trainee on the current date
        existing_entry = conn.execute(
            """SELECT * FROM Trainee_Exercises
               WHERE Trainee_ID = ? AND Exercise_ID = ? AND DATE(Timestamp) = ?""",
            (user_id, exercise_id, today_date)
        ).fetchone()

        if existing_entry:
            flash("You have already added this exercise for today.", "warning")
        else:
            # Insert a new entry
            conn.execute(
                """INSERT INTO Trainee_Exercises (Trainee_ID, Timestamp, Trainee_Calories_Burned, Exercise_ID)
                   VALUES (?, ?, ?, ?)""",
                (user_id, today_date, 0, exercise_id)  # Set Trainee_Calories_Burned to 0 or calculate if needed
            )
            conn.commit()
            flash("Exercise added successfully!", "success")
    except Exception as e:
        flash(f"An error occurred: {str(e)}", "danger")
    finally:
        conn.close()

    return redirect(url_for('GetExerciseDetails', exercise_id=exercise_id))


@app.route('/notifications')
def view_notifications():
    if 'User_ID' not in session:
        flash("You need to be logged in to view notifications.", "danger")
        return redirect(url_for('login'))

    user_id = session['User_ID']
    conn = get_db_connection()
    notifications = []
    try:

        today_date = datetime.now().strftime("%Y-%m-%d")
        print(f"Today's date: {today_date}")

        # Check if the trainee has logged any exercises today
        has_exercise_today = conn.execute(
            "SELECT * FROM Trainee_Exercise WHERE Trainee_ID = ? AND Timestamp = ?",
            (user_id, today_date)
        ).fetchone()
        print(f"Exercise records found for today: {has_exercise_today}")

        # Check if the trainee has logged any recipes today
        has_meals_today = conn.execute(
            "SELECT * FROM Trainee_Recipes WHERE Trainee_ID = ? AND Timestamp = ?",
            (user_id, today_date)
        ).fetchone()
        print(f"Recipe records found for today: {has_meals_today}")

        # Add notifications if no data is found
        if not has_exercise_today:
            notifications.append({
                'Message': "Don't forget to perform your exercise today!",
                'Timestamp': today_date
            })

        if not has_meals_today:
            notifications.append({
                'Message': "Don't forget to log your meals today!",
                'Timestamp': today_date
            })

    except Exception as e:
        flash(f"An error occurred: {str(e)}", "danger")
    finally:
        conn.close()

    if not notifications:
        notifications.append({
            'Message': "No notifications for today. Keep up the good work!",
            'Timestamp': today_date
        })

    return render_template('notification.html', notifications=notifications)


if __name__ == '__main__':
    app.run(host="127.0.0.1", port=5000, debug=True)
