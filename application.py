import os
import requests

from flask import Flask, render_template, request, session, jsonify, redirect
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from functools import wraps

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

def login_required(f):
    """
    Decorate routes to require login.
    http://flask.pocoo.org/docs/1.0/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/")
        return f(*args, **kwargs)
    return decorated_function

def check_login(f):
    """
    Decorate routes to require login.
    http://flask.pocoo.org/docs/1.0/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is not None:
            return redirect("/index")
        return f(*args, **kwargs)
    return decorated_function


@app.route('/', methods=['GET', 'POST'])
@check_login
def login():
    session.clear()
    if request.method == "POST":
        input_username = request.form.get('username')
        user = db.execute("SELECT * FROM users WHERE username = :username", {"username": input_username}).fetchone()
        if user is None:
            return render_template("error.html", message="No such user, try again.")
        else:
            input_password = request.form.get('password')
            if input_password == user[2]:
                #Store user
                session['user_id'] = user[0]
                return render_template('index.html')
            else:
                return render_template("error.html", message='Wrong password')
    return render_template('login.html')

@app.route('/index', methods=['GET', 'POST'])
@login_required
def index():
    if request.method == 'POST':
        search = request.form.get('search')
        if len(search) < 3:
            return render_template("error.html", message="Please search for more than 2 charaters")
        search = '%' + search + '%'
        books = db.execute("SELECT * FROM books WHERE LOWER(ISBN) LIKE LOWER(:search) OR LOWER(title) LIKE LOWER(:search) OR LOWER(author) LIKE LOWER(:search) ", {"search": search}).fetchall()
        return render_template('search.html', books=books)
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
@check_login
def register():
    if request.method == 'POST':
        input_username = request.form.get('username')
        input_password = request.form.get('password')
        user = db.execute("SELECT * FROM users WHERE username = :username", {"username": input_username}).fetchone()
        # no current user, good to go!
        if user is None and len(input_password) != 0:
            db.execute("INSERT INTO users (username, password) VALUES (:username, :password)",{"username": input_username,"password": input_password})
            db.commit()
            return render_template('login.html')
        else:
            return render_template("error.html", message='Registration fail, user or password error')
    return render_template('register.html')

@app.route("/books/<int:book_id>",methods=['GET','POST'])
@login_required
def books(book_id):
    if request.method == 'POST':
        user_id = session['user_id']
        past_review = db.execute("SELECT user_id, book_id FROM reviews WHERE user_id = :user_id AND book_id = :book_id",
        {"user_id": user_id, "book_id": book_id}).fetchone()
        if past_review is not None:
            return render_template('error.html', message='You already reviewed this book')
        score = request.form.get('score')
        review = request.form.get('review')
        db.execute("INSERT INTO reviews (book_id, user_id, score, review) VALUES (:book_id, :user_id, :score, :review)",
        {"book_id": book_id, "user_id": user_id, "score": score, "review": review})
        db.commit()
        return redirect(request.url)

    book = db.execute("SELECT * FROM books WHERE id = :id", {"id": book_id}).fetchone()
    if book is None:
        return render_template("error.html", message="No such book.")
    reviews = db.execute("SELECT * FROM reviews WHERE book_id = :id", {"id": book_id}).fetchall()
    score = 0
    if len(reviews) != 0:
        for review in reviews:
            score += review.score
        score = score/len(reviews)
    key = os.getenv("GOODREAD_KEY")
    get = requests.get("https://www.goodreads.com/book/review_counts.json",params={"key":key,"isbns": book.isbn})
    get = get.json()
    goodread_score = get["books"][0]["average_rating"]
    goodread_count = get["books"][0]["text_reviews_count"]
    return render_template("books.html", book=book, score=score, goodread_score=goodread_score, goodread_count=goodread_count)


@app.route("/api/<string:isbn>")
@login_required
def api(isbn):
    book = db.execute("SELECT * FROM books WHERE LOWER(ISBN) = LOWER(:isbn)", {"isbn": isbn.lower()}).fetchone()
    if book is None:
        return jsonify({"error": "No book isbn found"}), 422
    key = os.getenv("GOODREAD_KEY")
    get = requests.get("https://www.goodreads.com/book/review_counts.json",params={"key":key,"isbns": book.isbn})
    get = get.json()

    return jsonify({
        "title": book.title,
        "author": book.author,
        "year": book.year,
        "isbn": book.isbn,
        "review_count": get["books"][0]["text_reviews_count"],
        "average_score": get["books"][0]["average_rating"]
    })

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


