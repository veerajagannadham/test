from flask import Flask, render_template, request, redirect, url_for, session, flash, json
from sqlalchemy import create_engine, text
import pandas as pd
import numpy as np
import json
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'ce7583aac90d46c4846459342e69d0d7'  # Replace this with a strong secret key

# Database connection configuration for Azure MySQL
db_connection_config = {
    'user': 'admin_user',
    'password': 'Root123***',
    'host': 'azure-retail-webapp.mysql.database.azure.com',
    'database': 'azure_retail',
    'port': 3306
}

# Create SQLAlchemy engine with Azure MySQL connection
db_connection_string = f"mysql+pymysql://{db_connection_config['user']}:{db_connection_config['password']}@{db_connection_config['host']}:{db_connection_config['port']}/{db_connection_config['database']}?ssl_ca=DigiCertGlobalRootCA.crt.pem&ssl_verify_cert=true"
engine = create_engine(db_connection_string)

# Custom CSS function for Flask templates
def add_custom_css():
    return """
    <style>
        .alert {
            padding: 15px;
            margin-bottom: 20px;
            border: 1px solid transparent;
            border-radius: 4px;
        }
        .alert-success {
            color: #3c763d;
            background-color: #dff0d8;
            border-color: #d6e9c6;
        }
        .alert-danger {
            color: #a94442;
            background-color: #f2dede;
            border-color: #ebccd1;
        }
        .dashboard-container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        .dashboard-card {
            background: white;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
            padding: 20px;
            margin-bottom: 20px;
        }
        .nav-links {
            display: flex;
            justify-content: space-around;
            margin: 20px 0;
        }
        .nav-links a {
            padding: 10px 20px;
            background: #3498db;
            color: white;
            border-radius: 4px;
            text-decoration: none;
            transition: background-color 0.3s;
        }
        .nav-links a:hover {
            background: #2980b9;
            text-decoration: none;
        }
        .data-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        .data-table th, .data-table td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        .data-table th {
            background-color: #f5f7fa;
            font-weight: 600;
        }
        .data-table tr:hover {
            background-color: #f5f5f5;
        }
    </style>
    """

# Custom formatter for numbers in templates
@app.template_filter('format_number')
def format_number(value):
    if isinstance(value, (int, float)):
        if value >= 1000:
            return f"{value:,.2f}"
        else:
            return f"{value:.2f}"
    return value

# Routes
@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']

        try:
            insert_query = text("INSERT INTO users (username, password, email) VALUES (:username, :password, :email)")
            with engine.connect() as connection:
                connection.execute(insert_query, {"username": username, "password": password, "email": email})
                connection.commit()

            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash(f'Registration failed: {str(e)}', 'danger')

    return render_template('home.html', custom_css=add_custom_css())

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
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password.', 'danger')

    return render_template('login.html', custom_css=add_custom_css())

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        flash('Please log in to access the dashboard.', 'danger')
        return redirect(url_for('login'))
    
    try:
        # Check if there's transaction data
        check_query = text("SELECT COUNT(*) as count FROM transactions")
        with engine.connect() as connection:
            result = connection.execute(check_query)
            has_transactions = result.fetchone()[0] > 0
        
        if not has_transactions:
            return render_template('dashboard.html', 
                                  has_data=False, 
                                  custom_css=add_custom_css())
        
        # Load necessary data for the dashboard
        # 1. Get summary metrics
        metrics_query = text("""
            SELECT 
                SUM(spend) as total_sales,
                AVG(spend) as avg_order,
                COUNT(DISTINCT hshd_num) as total_customers,
                COUNT(*) as total_transactions
            FROM transactions
        """)
        
        with engine.connect() as connection:
            metrics_result = connection.execute(metrics_query)
            metrics = metrics_result.fetchone()
            
            total_sales = metrics[0] if metrics[0] else 0
            avg_order = metrics[1] if metrics[1] else 0
            total_customers = metrics[2] if metrics[2] else 0
            total_transactions = metrics[3] if metrics[3] else 0
        
        # 2. Get spend over time data
        spend_query = text("""
            SELECT 
                STR_TO_DATE(purchase_date, '%d-%b-%y') as date, 
                SUM(spend) as spend
            FROM transactions
            GROUP BY STR_TO_DATE(purchase_date, '%d-%b-%y')
            ORDER BY date
        """)
        
        with engine.connect() as connection:
            spend_result = connection.execute(spend_query)
            spend_data = []
            for row in spend_result:
                # Handle both string and date objects
                date_str = row.date.strftime('%Y-%m-%d') if hasattr(row.date, 'strftime') else str(row.date)
                spend_data.append({
                    "date": date_str,
                    "spend": float(row.spend)
                })
        
        # 3. Get product department data
        dept_query = text("""
            SELECT department, COUNT(*) as count
            FROM products
            GROUP BY department
            ORDER BY count DESC
            LIMIT 10
        """)
        
        with engine.connect() as connection:
            dept_result = connection.execute(dept_query)
            dept_data = [{"department": row[0], "count": int(row[1])} for row in dept_result]
        
        # 4. Get household composition data
        household_query = text("""
            SELECT hshd_composition, COUNT(*) as count
            FROM households
            GROUP BY hshd_composition
        """)
        
        with engine.connect() as connection:
            household_result = connection.execute(household_query)
            household_data = [{"composition": row[0], "count": int(row[1])} for row in household_result]
        
        # 5. Get store region data
        region_query = text("""
            SELECT store_r, COUNT(*) as count
            FROM transactions
            GROUP BY store_r
        """)
        
        with engine.connect() as connection:
            region_result = connection.execute(region_query)
            region_data = [{"region": row[0], "count": int(row[1])} for row in region_result]
        
        # 6. Get recent transactions
        recent_query = text("""
            SELECT hshd_num, basket_num, purchase_date, product_num, spend, units, store_r
            FROM transactions
            ORDER BY purchase_date DESC
            LIMIT 10
        """)
        
        with engine.connect() as connection:
            recent_result = connection.execute(recent_query)
            recent_transactions = []
            for row in recent_result:
                trans = {}
                for idx, col in enumerate(recent_result.keys()):
                    if col == 'purchase_date':
                        trans[col] = row[idx].strftime('%Y-%m-%d') if isinstance(row[idx], datetime) else str(row[idx])
                    elif col == 'spend':
                        trans[col] = float(row[idx])
                    else:
                        trans[col] = row[idx]
                recent_transactions.append(trans)

        return render_template('dashboard.html',
                              has_data=True,
                              total_sales=total_sales,
                              avg_order=avg_order,
                              total_customers=total_customers,
                              total_transactions=total_transactions,
                              spend_data=json.dumps(spend_data),
                              dept_data=json.dumps(dept_data),
                              household_data=json.dumps(household_data),
                              region_data=json.dumps(region_data),
                              recent_transactions=recent_transactions,
                              custom_css=add_custom_css())
    
    except Exception as e:
        flash(f"Error loading dashboard: {str(e)}", 'danger')
        return render_template('dashboard.html', 
                              has_data=False,
                              custom_css=add_custom_css())

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if 'username' not in session:
        flash('Please log in to access this page.', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        file = request.files['file']
        table_name = request.form['table_name']
        
        if not file:
            flash('No file selected.', 'danger')
            return redirect(url_for('upload'))
        
        try:
            df_upload = pd.read_csv(file)
            df_upload.columns = df_upload.columns.str.strip().str.lower()
            
            # If transactions table, limit to 10k rows
            if table_name.lower() == 'transactions':
                df_upload = df_upload.head(10000)
            
            df_upload.to_sql(table_name, engine, if_exists='replace', index=False)
            flash(f"Table {table_name} uploaded successfully with {len(df_upload)} records!", 'success')
        except Exception as e:
            flash(f"Error uploading data: {str(e)}", 'danger')

    return render_template('upload.html', custom_css=add_custom_css())

@app.route('/search', methods=['GET', 'POST'])
def search():
    if 'username' not in session:
        flash('Please log in to access this page.', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        hshd_num = request.form['hshd_num']
        try:
            query = text("""
                SELECT h.hshd_num, h.loyalty_flag, h.age_range, h.marital_status,
                       h.income_range, h.homeowner_desc, h.household_composition,
                       h.household_size, h.children, t.basket_num, t.purchase_date,
                       t.product_num, t.spend, t.units, t.store_region, p.department,
                       p.commodity, p.brand_type, p.natural_organic_flag
                FROM households h
                JOIN transactions t ON h.hshd_num = t.hshd_num
                JOIN products p ON t.product_num = p.product_num
                WHERE h.hshd_num = :hshd_num
                ORDER BY h.hshd_num, t.basket_num, t.purchase_date, p.product_num
            """)
            result = pd.read_sql(query, engine, params={"hshd_num": hshd_num})
            
            if result.empty:
                flash(f"No data found for household number {hshd_num}", 'warning')
                return render_template('search.html', custom_css=add_custom_css())
            
            # Convert to HTML with better styling
            return f"""
            {add_custom_css()}
            <div class="dashboard-container">
                <div class="dashboard-card">
                    <h2>Search Results for Household {hshd_num}</h2>
                    <div style="overflow-x: auto;">
                        {result.to_html(classes='data-table', index=False)}
                    </div>
                    <div class="nav-links">
                        <a href="/search">New Search</a>
                        <a href="/dashboard">Back to Dashboard</a>
                    </div>
                </div>
            </div>
            """
        except Exception as e:
            flash(f"Error searching data: {str(e)}", 'danger')

    return render_template('search.html', custom_css=add_custom_css())

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('login'))

if __name__ == "__main__":
    app.run(debug=True)