from flask import Flask, render_template, request, redirect, url_for, session, g
import sqlite3
from datetime import datetime, timedelta
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'your_secret_key'
DATABASE = 'expense_tracker.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

@app.before_request
def load_user():
    g.user = session.get('user_id')

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        
        conn = get_db_connection()
        try:
            conn.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            conn.commit()
            conn.close()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            conn.close()
            error = 'Username already exists!'
    return render_template('register.html', error=error)

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            return redirect(url_for('dashboard'))
        else:
            error = 'Invalid credentials'
    return render_template('login.html',error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    message = None
    category = None

    if request.method == 'POST':
        username = request.form['username']
        new_password = request.form['new_password']

        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if user:
            hashed_password = generate_password_hash(new_password)
            conn.execute("UPDATE users SET password = ? WHERE username = ?", (hashed_password, username))
            conn.commit()
            message = "Password updated successfully. You can now log in."
            category = "success"
        else:
            message = "Username not found."
            category = "danger"
        conn.close()

    return render_template('reset_password.html', message=message, category=category)

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if not g.user:
        return redirect(url_for('login'))

    conn = get_db_connection()
    user_id = g.user

    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    query = "SELECT * FROM expenses WHERE user_id = ?"
    params = [user_id]

    if start_date and end_date:
        query += " AND date BETWEEN ? AND ?"
        params.extend([start_date, end_date])

    expenses = conn.execute(query + " ORDER BY date DESC", params).fetchall()

    week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    month_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

    weekly_total = conn.execute(
        "SELECT SUM(amount) FROM expenses WHERE user_id = ? AND date >= ?", (user_id, week_ago)
    ).fetchone()[0] or 0

    monthly_total = conn.execute(
        "SELECT SUM(amount) FROM expenses WHERE user_id = ? AND date >= ?", (user_id, month_ago)
    ).fetchone()[0] or 0

    # ✅ Pie chart data with filters
    if start_date and end_date:
        rows = conn.execute(
            "SELECT category, SUM(amount) as total FROM expenses WHERE user_id = ? AND date BETWEEN ? AND ? GROUP BY category",
            (user_id, start_date, end_date)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT category, SUM(amount) as total FROM expenses WHERE user_id = ? GROUP BY category",
            (user_id,)
        ).fetchall()

    chart_data = [{'category': row['category'], 'total': row['total']} for row in rows]
    conn.close()

    return render_template('dashboard.html', expenses=expenses, weekly_total=weekly_total,
                           monthly_total=monthly_total, start_date=start_date,
                           end_date=end_date, chart_data=chart_data)


@app.route('/add_expense', methods=['POST'])
def add_expense():
    if not g.user:
        return redirect(url_for('login'))

    user_id = g.user
    amount = float(request.form['amount'])
    category = request.form['category']
    description = request.form['description']
    date = request.form['date']

    conn = get_db_connection()
    conn.execute("INSERT INTO expenses (user_id, amount, category, description, date) VALUES (?, ?, ?, ?, ?)",
                 (user_id, amount, category, description, date))
    conn.commit()
    conn.close()

    return redirect(url_for('dashboard'))

@app.route('/edit/<int:expense_id>', methods=['GET', 'POST'])
def edit_expense(expense_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    expense = conn.execute('SELECT * FROM expenses WHERE id = ? AND user_id = ?', (expense_id, session['user_id'])).fetchone()

    if not expense:
        conn.close()
        return 'Expense not found', 404

    if request.method == 'POST':
        category = request.form['category']
        amount = request.form['amount']
        date = request.form['date']
        conn.execute('UPDATE expenses SET category = ?, amount = ?, date = ? WHERE id = ?', (category, amount, date, expense_id))
        conn.commit()
        conn.close()
        return redirect(url_for('dashboard'))

    conn.close()
    return render_template('edit_expense.html', expense=expense)

@app.route('/delete/<int:expense_id>')
def delete_expense(expense_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    conn.execute('DELETE FROM expenses WHERE id = ? AND user_id = ?', (expense_id, session['user_id']))
    conn.commit()
    conn.close()
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    if not os.path.exists(DATABASE):
        conn = get_db_connection()
        with open('schema.sql') as f:
            conn.executescript(f.read())
        conn.close()
    app.run(debug=True)
