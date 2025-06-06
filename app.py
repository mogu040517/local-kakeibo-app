from flask import Flask, render_template, request, redirect, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import os
import mysql.connector

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')

def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )

@app.route('/')
def index():
    return redirect('/login')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        password_hash = generate_password_hash(password)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)", 
                       (username, email, password_hash))
        conn.commit()
        conn.close()

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect('/balance_summary')
        else:
            flash("メールアドレスまたはパスワードが間違っています")

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/add_record', methods=['GET', 'POST'])
def add_record():
    # ログインしていない場合はログインページへ
    if 'user_id' not in session:
        return redirect('/login')

    if request.method == 'POST':
        date = request.form['date']
        category = request.form['category']
        amount = int(request.form['amount'])
        record_type = request.form['type']  # 'income' or 'expense'

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO records (user_id, date, category, amount, type)
            VALUES (%s, %s, %s, %s, %s)
        """, (session['user_id'], date, category, amount, record_type))
        conn.commit()
        conn.close()

        return redirect('/add_record')  # 登録後トップページへ

    return render_template('add_record.html')

@app.route('/records')
def records():
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, date, category, amount, type
        FROM records
        WHERE user_id = %s
        ORDER BY date DESC
    """, (session['user_id'],))
    records = cursor.fetchall()
    conn.close()

    return render_template('records.html', records=records)

@app.route('/delete_record/<int:id>', methods=['POST'])
def delete_record(id):
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        DELETE FROM records
        WHERE id = %s AND user_id = %s
    """, (id, session['user_id']))
    conn.commit()
    conn.close()

    return redirect('/records')

@app.route('/monthly_summary')
def monthly_summary():
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT
            DATE_FORMAT(date, '%Y-%m') AS month,
            SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) AS total_income,
            SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END) AS total_expense
        FROM records
        WHERE user_id = %s
        GROUP BY month
        ORDER BY month DESC
    """, (session['user_id'],))
    summary = cursor.fetchall()
    conn.close()

    return render_template('monthly_summary.html', summary=summary)

@app.route('/category_summary')
def category_summary():
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT
            YEAR(date) AS year,
            category,
            SUM(amount) AS total_expense
        FROM records
        WHERE user_id = %s
          AND type = 'expense'
        GROUP BY year, category
        ORDER BY year DESC, category ASC
    """, (session['user_id'],))
    summary = cursor.fetchall()
    conn.close()

    return render_template('category_summary.html', summary=summary)

@app.route('/balance_summary')
def balance_summary():
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            YEAR(date) AS year,
            SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) AS income,
            SUM(CASE WHEN type = 'expense' AND category = '交通費' THEN amount ELSE 0 END) AS transport,
            SUM(CASE WHEN type = 'expense' AND category != '交通費' THEN amount ELSE 0 END) AS other_expense
        FROM records
        WHERE user_id = %s
        GROUP BY year
        ORDER BY year DESC
    """, (session['user_id'],))
    results = cursor.fetchall()
    conn.close()

    # 計算列を追加
    for row in results:
        row["所得"] = row["income"] - row["transport"]
        row["残高"] = row["所得"] - row["other_expense"]

    return render_template("balance_summary.html", summary=results)

if __name__ == '__main__':
    app.run(debug=True)
