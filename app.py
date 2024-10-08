import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime


from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")
# db.execute("CREATE TABLE transactions (user_id int, symbol text, shares int, price float, time timestamp)") CREATING TRANSACTIONS TABLE
# db.execute("CREATE TABLE portfolio (user_id int, symbol text, shares int, price float)") CREATE PORTFOLIO
stocks2 = []


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    stocks = db.execute(
        "SELECT symbol, shares, price FROM transactions WHERE user_id = ?", session["user_id"])
    current_cash = (db.execute("SELECT cash FROM users WHERE id = ?",
                    session["user_id"]))[0]['cash']
    grand_total = current_cash
    stocks2 = []
    for stock in stocks:
        price2 = str(stock["price"])
        try:
            shares = int(stock["shares"])
            price = float(price2.strip("$").replace(",", ""))
        except ValueError:
            continue
        total = price * shares
        data = {
            "name": stock["symbol"],
            "price": price,
            "shares": shares,
            "total": total
        }
        stocks2.append(data)
        grand_total += total
    return render_template("index.html", stocks2=stocks2, grand_total=grand_total, current_cash=current_cash)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "POST":
        if request.form.get("symbol") == "" or lookup(request.form.get("symbol")) == None:
            return apology("Invalid Symbol", 400)
        if not request.form.get("shares").isdigit():
            return apology("Must Input Numbers", 400)
        if float(request.form.get("shares")) < 1:
            return apology("Invalid Number of Shares", 400)
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        quote = lookup(symbol.upper())
        price = float(quote["price"])
        total_cost = price * int(shares)
        cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"]
        if cash < total_cost:
            return apology("Insufficient Funds")
        usdPrice = usd(price)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.execute("UPDATE users SET cash = cash - ? WHERE id = ?",
                   usd(total_cost), session["user_id"])
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price, time) VALUES (?, ?, ?, ?, ?)",
                   session["user_id"], symbol, shares, usdPrice, current_time)

        return redirect("/")
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    history = db.execute("SELECT * FROM transactions WHERE user_id = ?", session["user_id"])
    return render_template("history.html", history=history)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "POST":
        quotes = lookup(request.form.get("symbol").upper())
        if quotes == None:
            return apology("Invalid Stock Symbol", 400)
        stocks = {"symbol": quotes["symbol"],
                  "price": usd(float(quotes["price"]))}
        return render_template("quoted.html", stocks=stocks)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if (request.method == "POST"):
        if (request.form.get("username") == "" or request.form.get("password") == "" or request.form.get("confirmation") == ""):
            return apology("Invalid Username and/or Password", 400)
        if (request.form.get("password") != request.form.get("confirmation")):
            return apology("Passwords do not match", 400)

        hashPassword = generate_password_hash(request.form.get("password"))

        try:
            db.execute("INSERT INTO users (username, hash) VALUES (?, ?)",
                       request.form.get("username"), hashPassword)
        except ValueError:
            return apology("Username is already taken", 400)
        session["user_id"] = (db.execute(
            "SELECT id FROM users WHERE username = ?", request.form.get("username")))[0]['id']
        return redirect("/")
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "POST":
        # Handle form submission
        call = request.form.get('select').upper()
        shareCall = int(request.form.get("sellshares"))

        # Validate stock symbol
        if lookup(call) is None or call == "":
            return apology("Invalid Stock Symbol", 400)
        if shareCall < 1:
            return apology("Invalid # of shares", 400)

        # Fetch owned symbols
        symbols = [item["symbol"] for item in db.execute(
            "SELECT symbol FROM transactions WHERE user_id = ?", session["user_id"])]
        if call not in symbols:
            return apology("Stock not owned", 400)

        # Get stock quote and check funds
        quote = lookup(call)
        price = quote["price"]
        cost = shareCall * price
        currentCash = db.execute("SELECT cash FROM users WHERE id=?", session["user_id"])[0]['cash']
        if cost > currentCash:
            return apology("Insufficient Funds", 400)

        # Update database
        db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", cost, session["user_id"])
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price) VALUES (?, ?, ?, ?)",
                   session["user_id"], call, shareCall, price)
        db.execute("DELETE FROM transactions WHERE user_id = ? AND symbol = ? AND shares = ?",
                   session["user_id"], call, shareCall)
        flash(f"Sold {shareCall} shares of {call} at {usd(price)}")
        return redirect("/")

    else:
        # Handle GET request
        symbols = [item["symbol"] for item in db.execute(
            "SELECT symbol FROM transactions WHERE user_id = ?", session["user_id"])]
        return render_template("sell.html", symbol=symbols)
