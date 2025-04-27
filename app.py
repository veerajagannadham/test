from flask import Flask, render_template, request, redirect, url_for, session
from sqlalchemy import create_engine, text
import pandas as pd
import dash
import cryptography
from dash import dcc, html

app = Flask(__name__)
app.secret_key = 'e0e711af1df57f831a842d5d602c2652b1d7c7459f5328e61078634579bd797f'  # Replace this with a strong secret key

# Database connection
db_connection_string = 'admin_user@azure-retail-webapp.mysql.database.azure.com:3306'
engine = create_engine(db_connection_string)

# Integrate Dash into Flask
external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']
dash_app = dash.Dash(__name__, server=app, url_base_pathname='/dashboard/', external_stylesheets=external_stylesheets)

# Load data for dashboard
def serve_layout():
    try:
        df = pd.read_sql('SELECT * FROM transactions', engine)
        df.columns = df.columns.str.strip().str.lower()

        if not df.empty and 'purchase_date' in df.columns and 'spend' in df.columns:
            return html.Div([
                html.Div([
                html.H1('Retail Insights Dashboard'),
                dcc.Graph(
                    figure={
                        'data': [{
                            'x': pd.to_datetime(df['purchase_date']),
                            'y': df['spend'],
                            'type': 'bar',
                            'name': 'Spend'
                        }],
                        'layout': {
                            'title': 'Customer Spend Over Time',
                            'xaxis': {'title': 'Date'},
                            'yaxis': {'title': 'Spend'}
                        }
                    }
                ),
                ]),
                html.Div([
                html.Br(),
                html.A('Upload New Data', href='/upload'),
                html.Br(),
                html.A('Search Household', href='/search'),
                html.Br(),
                html.A('Logout', href='/logout')
            ]),
            ])
        else:
            return html.Div([
                html.H1('No transaction data available. Please upload transactions first.'),
                html.Br(),
                html.A('Upload New Data', href='/upload'),
                html.Br(),
                html.A('Search Household', href='/search'),
                html.Br(),
                html.A('Logout', href='/logout')
            ])
    except Exception as e:
        return html.Div([
            html.H1('Error loading dashboard!'),
            html.P(str(e))
        ])

dash_app.layout = serve_layout

# Routes
@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']

        insert_query = text("INSERT INTO users (username, password, email) VALUES (:username, :password, :email)")
        with engine.connect() as connection:
            connection.execute(insert_query, {"username": username, "password": password, "email": email})
            connection.commit()

        return redirect(url_for('login'))
    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        query = text("SELECT * FROM users WHERE username=:username AND password=:password")
        with engine.connect() as connection:
            result = connection.execute(query, {"username": username, "password": password})
            user = result.fetchone()

        if user:
            session['username'] = username
            return redirect('/dashboard/')
        else:
            return "Invalid username or password."

    return render_template('login.html')

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if 'username' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        file = request.files['file']
        table_name = request.form['table_name']
        df_upload = pd.read_csv(file)
        df_upload.columns = df_upload.columns.str.strip().str.lower()  # STRIP SPACES here
         # If transactions table, limit to 10k rows
        if table_name.lower() == 'transactions':
            df_upload = df_upload.head(10000)
        df_upload.to_sql(table_name, engine, if_exists='replace', index=False)
        return f"Table {table_name} uploaded successfully!"

    return render_template('upload.html')

@app.route('/search', methods=['GET', 'POST'])
def search():
    if 'username' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        hshd_num = request.form['hshd_num']
        query = text("""
            SELECT *
            FROM households h
            JOIN transactions t ON h.hshd_num = t.hshd_num
            JOIN products p ON t.product_num = p.product_num
            WHERE h.hshd_num = :hshd_num
            ORDER BY h.hshd_num, t.basket_num, t.purchase_date, p.product_num
        """)
        result = pd.read_sql(query, engine, params={"hshd_num": hshd_num})
        return result.to_html()

    return render_template('search.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

if __name__ == "__main__":
    app.run(debug=True)
