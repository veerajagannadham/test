

from flask import Flask, render_template, request, redirect, url_for, session, flash, json
from sqlalchemy import create_engine, text
import pandas as pd
import numpy as np
import json
from datetime import datetime

app = Flask(__name__)
app.secret_key = "ce7583aac90d46c4846459342e69d0d7"  # Replace with a strong secret key

# Database configuration for Azure MySQL
db_connection_config = {
    "user": "admin_user",
    "password": "Root123***",
    "host": "azure-retail-webapp.mysql.database.azure.com",
    "database": "azure_retail",
    "port": 3306,
}

# Connection string
db_connection_string = (
    f"mysql+pymysql://{db_connection_config['user']}:{db_connection_config['password']}"
    f"@{db_connection_config['host']}:{db_connection_config['port']}/{db_connection_config['database']}"
    "?ssl_ca=DigiCertGlobalRootCA.crt.pem&ssl_verify_cert=true"
)
engine = create_engine(db_connection_string)


# Custom CSS for templates
def add_custom_css():
    return """
    <style>
        /* Your custom styles here */
    </style>
    """

# Template filter for formatting numbers
@app.template_filter("format_number")
def format_number(value):
    if isinstance(value, (int, float)):
        return f"{value:,.2f}" if value >= 1000 else f"{value:.2f}"
    return value

# Routes
@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        email = request.form["email"]
        try:
            insert_query = text(
                "INSERT INTO users (username, password, email) VALUES (:username, :password, :email)"
            )
            with engine.connect() as connection:
                connection.execute(insert_query, {"username": username, "password": password, "email": email})

            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("login"))
        except Exception as e:
            flash(f"Registration failed: {str(e)}", "danger")

    return render_template("home.html", custom_css=add_custom_css())

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        query = text("SELECT * FROM users WHERE username=:username AND password=:password")
        with engine.connect() as connection:
            user = connection.execute(query, {"username": username, "password": password}).fetchone()

        if user:
            session["username"] = username
            flash("Login successful!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid username or password.", "danger")

    return render_template("login.html", custom_css=add_custom_css())

@app.route("/dashboard")
def dashboard():
    if "username" not in session:
        flash("Please log in to access the dashboard.", "danger")
        return redirect(url_for("login"))

    try:
        with engine.connect() as connection:
            # Check if transactions exist
            check_query = text("SELECT COUNT(*) as count FROM transactions")
            has_transactions = connection.execute(check_query).scalar() > 0

            if not has_transactions:
                return render_template("dashboard.html", has_data=False, custom_css=add_custom_css())

            # Get metrics
            metrics_query = text("""
                SELECT 
                    SUM(spend) as total_sales,
                    AVG(spend) as avg_order,
                    COUNT(DISTINCT hshd_num) as total_customers,
                    COUNT(*) as total_transactions
                FROM transactions
            """)
            metrics = connection.execute(metrics_query).fetchone()
            metrics = {
                "total_sales": metrics[0] or 0,
                "avg_order": metrics[1] or 0,
                "total_customers": metrics[2] or 0,
                "total_transactions": metrics[3] or 0
            }

            # Get spend data
            spend_query = text("""
                SELECT purchase_date as date, SUM(spend) as spend
                FROM transactions
                GROUP BY purchase_date
                ORDER BY purchase_date
            """)
            spend_data = [
                {"date": str(row.date), "spend": float(row.spend)} 
                for row in connection.execute(spend_query)
            ]

            # Get department data
            dept_query = text("""
                SELECT department, COUNT(*) as count
                FROM products
                GROUP BY department
                ORDER BY count DESC
                LIMIT 10
            """)
            dept_data = [
                {"department": row.department, "count": int(row.count)} 
                for row in connection.execute(dept_query)
            ]

            # Get household data
            household_query = text("""
                SELECT hshd_composition, COUNT(*) as count
                FROM households
                GROUP BY hshd_composition
            """)
            household_data = [
                {"composition": row.hshd_composition, "count": int(row.count)} 
                for row in connection.execute(household_query)
            ]

            # Get region data
            region_query = text("""
                SELECT store_r, COUNT(*) as count
                FROM transactions
                GROUP BY store_r
            """)
            region_data = [
                {"region": row.store_r, "count": int(row.count)} 
                for row in connection.execute(region_query)
            ]

            # Get recent transactions (fixed dictionary conversion)
            recent_query = text("""
                SELECT hshd_num, basket_num, purchase_date, product_num, spend, units, store_r
                FROM transactions
                ORDER BY purchase_date DESC
                LIMIT 10
            """)
            recent_transactions = []
            for row in connection.execute(recent_query):
                trans = {
                    "hshd_num": row.hshd_num,
                    "basket_num": row.basket_num,
                    "purchase_date": str(row.purchase_date),
                    "product_num": row.product_num,
                    "spend": float(row.spend),
                    "units": row.units,
                    "store_region": row.store_r  # Changed to match template
                }
                recent_transactions.append(trans)

        return render_template(
            "dashboard.html",
            has_data=True,
            total_sales=metrics["total_sales"],
            avg_order=metrics["avg_order"],
            total_customers=metrics["total_customers"],
            total_transactions=metrics["total_transactions"],
            spend_data=json.dumps(spend_data),
            dept_data=json.dumps(dept_data),
            household_data=json.dumps(household_data),
            region_data=json.dumps(region_data),
            recent_transactions=recent_transactions,
            custom_css=add_custom_css(),
        )

    except Exception as e:
        flash(f"Error loading dashboard: {str(e)}", "danger")
        return render_template("dashboard.html", has_data=False, custom_css=add_custom_css())

@app.route("/upload", methods=["GET", "POST"])
def upload():
    if "username" not in session:
        flash("Please log in to access this page.", "danger")
        return redirect(url_for("login"))

    if request.method == "POST":
        file = request.files["file"]
        table_name = request.form["table_name"]

        if not file:
            flash("No file selected.", "danger")
            return redirect(url_for("upload"))

        try:
            df_upload = pd.read_csv(file)
            df_upload.columns = df_upload.columns.str.strip().str.lower()

            if table_name.lower() == "transactions":
                df_upload = df_upload.head(10000)

            df_upload.to_sql(table_name, engine, if_exists="replace", index=False)
            flash(f"Table {table_name} uploaded successfully with {len(df_upload)} records!", "success")
        except Exception as e:
            flash(f"Error uploading data: {str(e)}", "danger")

    return render_template("upload.html", custom_css=add_custom_css())

@app.route('/search', methods=['GET', 'POST'])
def search():
    if 'username' not in session:
        flash('Please log in to access this page.', 'danger')
        return redirect(url_for('login'))

    household_info = None
    transactions = None
    
    if request.method == 'POST':
        hshd_num = request.form.get('hshd_num', '').strip()
        if not hshd_num:
            flash('Please enter a household number', 'warning')
            return render_template('search.html', custom_css=add_custom_css())
        
        try:
            with engine.connect() as conn:
                # Get household info - explicitly specify columns
                household_query = text("""
                    SELECT hshd_num, age_range, marital, 
                           income_range, hshd_composition, hh_size
                    FROM households 
                    WHERE hshd_num = :hshd_num 
                    LIMIT 1
                """)
                household_result = conn.execute(household_query, {"hshd_num": hshd_num}).fetchone()
                
                if household_result:
                    # Convert to dictionary manually
                    household_info = {
                        'hshd_num': household_result.hshd_num,
                        'age_range': household_result.age_range,
                        'marital_status': household_result.marital,
                        'income_range': household_result.income_range,
                        'hshd_composition': household_result.hshd_composition,
                        'household_size': household_result.hh_size
                    }
                
                # Get transactions with basic product info
                transaction_query = text("""
                    SELECT 
                        t.basket_num, 
                        t.purchase_date, 
                        t.product_num, 
                        t.spend, 
                        t.units, 
                        t.store_r as store_region,
                        p.department,
                        p.commodity
                    FROM transactions t
                    LEFT JOIN products p ON t.product_num = p.product_num
                    WHERE t.hshd_num = :hshd_num
                    ORDER BY t.purchase_date DESC
                    LIMIT 100
                """)
                
                transaction_result = conn.execute(transaction_query, {"hshd_num": hshd_num}).fetchall()
                
                if transaction_result:
                    transactions = []
                    for row in transaction_result:
                        transactions.append({
                            'basket_num': row.basket_num,
                            'purchase_date': str(row.purchase_date),
                            'product_num': row.product_num,
                            'spend': float(row.spend),
                            'units': row.units,
                            'store_region': row.store_region,
                            'department': row.department,
                            'commodity': row.commodity
                        })
                
                if not household_info and not transactions:
                    flash(f"No data found for household {hshd_num}", 'info')
                
        except Exception as e:
            flash(f"Error searching data: {str(e)}", 'danger')
            app.logger.error(f"Search error: {str(e)}")

    return render_template('search.html',
                         household_info=household_info,
                         transactions=transactions,
                         custom_css=add_custom_css())

@app.route("/analytics")
def analytics():
    if "username" not in session:
        flash("Please log in to access this page.", "danger")
        return redirect(url_for("login"))
    
    return render_template("analytics.html", custom_css=add_custom_css())

@app.route("/logout")
def logout():
    session.pop("username", None)
    flash("You have been logged out successfully.", "success")
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True)
