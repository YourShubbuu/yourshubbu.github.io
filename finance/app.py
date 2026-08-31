import os
import random
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

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
    """Show portfolio of stocks"""
    user_id = session["user_id"]
    user = db.execute("SELECT * FROM users WHERE id = ?", user_id)
    username = user[0]["username"]
    cash = user[0]["cash"]
    stocks = db.execute("SELECT * FROM portfolio WHERE user_id = ?", user_id)
    grand_total = cash
    for stock in stocks:
        newstock = lookup(stock["symbol"])
        current_price = newstock["price"]
        grand_total += current_price*(stock["shares"])
        shares = db.execute("SELECT shares FROM portfolio WHERE symbol = ? AND user_id = ?", stock["symbol"], user_id)
        stock["total"] = shares[0]["shares"] * current_price

    return render_template("index.html", username=username, cash=cash, stocks=stocks, grand_total=grand_total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        try:
            shares = int(request.form.get("shares"))
        except ValueError:
            return apology("Someone should teach you what numbers are ;-;", 400)
        except TypeError:
            return apology("Enter a symbol OMG!!", 400)

        if shares <= 0:
            return apology("Buy atleast 1 share IDIOT!!", 400)

        qt = lookup(symbol)

        if qt is None:
            return apology("ENTER A VALID STOCK NAME GODDAMNIT!!", 400)

        symbol = qt["symbol"]

        price = qt["price"]


        user_id = session["user_id"]
        user = db.execute("SELECT * FROM users WHERE id = ?", user_id)
        cash = user[0]["cash"]

        cost = price * shares
        if cash - cost < 0:
            return apology("You're broke man XD", 400)

        transaction_id = random.randint(1000000000, 9999999999)
        db.execute("INSERT INTO transactions (id, shares, symbol, price, type, user_id) VALUES (?, ?, ?, ?, 'BUY', ?)", transaction_id, shares, symbol, price, user_id)

        cash -= cost

        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash, user_id)

        if not db.execute("SELECT * FROM portfolio WHERE user_id = ? AND symbol = ?", user_id, symbol):
            db.execute("INSERT INTO portfolio (user_id, buy_price, shares, symbol) VALUES (?, ?, ?, ?)", user[0]["id"], price, shares, symbol)

        else:
            old_price = db.execute("SELECT buy_price FROM portfolio WHERE symbol = ? AND user_id = ?", symbol, user_id)
            old_shares = db.execute("SELECT shares FROM portfolio WHERE symbol = ? AND user_id = ?", symbol, user_id)
            avg = ((price * shares) + (old_price[0]["buy_price"] * old_shares[0]["shares"]))/(shares + old_shares[0]["shares"])
            shares += old_shares[0]["shares"]
            db.execute("UPDATE portfolio SET shares = ?, buy_price = ? WHERE user_id = ?", shares, avg, user_id)

        flash("Stock purchased successfully!")
        return redirect("/")

    else:
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user_id = session["user_id"]
    transactions = db.execute("SELECT * FROM transactions WHERE user_id = ?", user_id)
    return render_template("history.html",transactions=transactions)


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
    """Get stock quote."""
    if request.method == "POST":
        symbol = request.form.get("symbol")

        if not symbol:
            return apology("Enter a symbol OMG!!", 400)

        qt = lookup(symbol)

        if qt is None:
            return apology("ENTER A VALID STOCK NAME GODDAMNIT!!", 400)

        return render_template("quoted.html", name=qt["name"], symbol=qt["symbol"], price=qt["price"])

    else:
        return render_template("quote.html")



@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        if not request.form.get("username"):
            return apology("give the username idiot!!", 400)
        elif not request.form.get("password"):
            return apology("who will enter password!!??", 400)
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("Passwords do not match")
        elif db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username")):
            return apology("Username is already taken!!!", 400)

        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", request.form.get("username"), generate_password_hash(request.form.get("password")))

        rows = db.execute("SELECT id FROM users WHERE username = ?", request.form.get("username"))

        session["user_id"] = rows[0]["id"]

        flash("Registered!")
        return redirect("/")

    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    user_id = session["user_id"]
    stocks = db.execute("SELECT * FROM portfolio WHERE user_id = ?", user_id)
    if request.method == "POST":
        try:
            sym = request.form.get("symbol")
            if not sym:
                return apology("Ester egg: my name is shubh", 400)
        except ValueError:
            return apology("Are you trying to act dumb?", 400)
        x = None
        for i in range(len(stocks)):
            if  sym == stocks[i]["symbol"]:
                x = i
                break
        if x == None:
            return apology("You don't own that smarty", 400)

        try:
            shares = int(request.form.get("shares"))
        except ValueError:
            return apology("Hey siri, tell this idiot what are shares", 400)
        except TypeError:
            return apology("You just missed an ester egg", 400)
        if shares > stocks[x]["shares"]:
            return apology("Bro thinks he has too much shares", 400)
        if shares <= 0:
            return apology("Look at you go retard!", 400)
        user = db.execute("SELECT * FROM users WHERE id = ?", user_id)
        cash = user[0]["cash"]
        new_price = lookup(sym)
        cash += shares*new_price["price"]
        if stocks[x]["shares"] - shares == 0:
            db.execute("DELETE FROM portfolio WHERE user_id = ? AND symbol = ?", user_id, sym)
        db.execute("UPDATE portfolio SET shares = ? WHERE user_id = ? AND symbol = ?", stocks[x]["shares"] - shares, user_id, sym)
        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash, user_id)
        transaction_id = random.randint(1000000000, 9999999999)
        db.execute("INSERT INTO transactions (id, shares, symbol, price, type, user_id) VALUES (?, ?, ?, ?, 'SELL', ?)", transaction_id, shares, sym, new_price["price"], user_id)

        flash("Stock sold successfully!")
        return redirect("/")

    else:
        return render_template("sell.html", stocks=stocks)
