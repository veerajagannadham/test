# run_analytics.py
import os
import json
import pandas as pd
import matplotlib.pyplot as plt
from sqlalchemy import create_engine
import importlib.util
import sys

# Create directories for outputs
os.makedirs('static/images', exist_ok=True)
os.makedirs('static/data', exist_ok=True)

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

# Function to load a module from file path
def load_module_from_path(module_name, file_path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

# Modified versions of the scripts that save outputs
def run_basket_analysis():
    engine = create_engine(db_connection_string)
    metrics = {}
    
    # Load the data
    transactions = pd.read_sql('SELECT * FROM transactions', engine)
    
    # Data Cleaning
    transactions['spend'] = pd.to_numeric(transactions['spend'], errors='coerce')
    transactions['units'] = pd.to_numeric(transactions['units'], errors='coerce')
    transactions = transactions.dropna(subset=['spend', 'units'])
    
    # Feature Engineering
    transactions['high_purchase'] = (transactions['units'] > 3).astype(int)
    
    # Calculate metrics
    metrics['avg_spend'] = f"${transactions['spend'].mean():.2f}"
    metrics['high_purchase_rate'] = f"{(transactions['high_purchase'].mean() * 100):.1f}%"
    
    # Prepare features and labels
    X = transactions[['spend', 'units']]
    y = transactions['high_purchase']
    
    # Train-Test Split
    from sklearn.model_selection import train_test_split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Model Training
    from sklearn.ensemble import RandomForestClassifier
    clf = RandomForestClassifier(n_estimators=100, random_state=42)
    clf.fit(X_train, y_train)
    
    # Model Evaluation
    from sklearn.metrics import classification_report, confusion_matrix
    y_pred = clf.predict(X_test)
    
    train_accuracy = clf.score(X_train, y_train)
    test_accuracy = clf.score(X_test, y_test)
    
    metrics['model_accuracy'] = f"{test_accuracy * 100:.1f}%"
    
    # Visualization
    plt.figure(figsize=(10,8))
    plt.scatter(transactions['spend'], transactions['units'], c=transactions['high_purchase'], cmap='coolwarm', alpha=0.6)
    plt.title('Spend vs Units (colored by High Purchase)')
    plt.xlabel('Spend')
    plt.ylabel('Units')
    plt.colorbar(label='High Purchase (0 = No, 1 = Yes)')
    plt.grid(True)
    plt.tight_layout()
    plt.savefig('static/images/basket_analysis.png', dpi=300)
    plt.close()
    
    # Save metrics
    with open('static/data/basket_analysis_metrics.json', 'w') as f:
        json.dump(metrics, f)
    
    return metrics

def run_churn_prediction():
    engine = create_engine(db_connection_string)
    metrics = {}
    
    # Load data
    transactions = pd.read_sql('SELECT * FROM transactions', engine)
    
    # Data Cleaning
    transactions['purchase_date'] = pd.to_datetime(transactions['purchase_date'], errors='coerce')
    transactions['spend'] = pd.to_numeric(transactions['spend'], errors='coerce')
    transactions = transactions.dropna(subset=['purchase_date', 'spend', 'hshd_num'])
    
    # Feature Engineering
    transactions['month'] = transactions['purchase_date'].dt.month
    monthly_spend = transactions.groupby(['hshd_num', 'month']).agg({'spend':'sum'}).reset_index()
    pivot = monthly_spend.pivot(index='hshd_num', columns='month', values='spend').fillna(0)
    
    # Create churn label
    pivot['churn_risk'] = (pivot[8] < pivot[7]*0.5).astype(int)
    
    # Calculate metrics
    metrics['churn_rate'] = f"{pivot['churn_risk'].mean() * 100:.1f}%"
    metrics['at_risk_households'] = str(int(pivot['churn_risk'].sum()))
    
    # Train-Test Split
    from sklearn.model_selection import train_test_split
    X = pivot.drop('churn_risk', axis=1)
    y = pivot['churn_risk']
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Model Training
    from sklearn.ensemble import RandomForestClassifier
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    
    # Predictions
    from sklearn.metrics import classification_report, confusion_matrix, precision_score
    y_pred = model.predict(X_test)
    
    # Calculate precision
    precision = precision_score(y_test, y_pred)
    metrics['model_precision'] = f"{precision * 100:.1f}%"
    
    # Visualization
    plt.figure(figsize=(10,8))
    pivot['churn_risk'].value_counts().plot(kind='bar')
    plt.title('Churn Risk Distribution')
    plt.xlabel('Churn Risk (0 = No, 1 = Yes)')
    plt.ylabel('Number of Households')
    plt.tight_layout()
    plt.savefig('static/images/churn_prediction.png', dpi=300)
    plt.close()
    
    # Save metrics
    with open('static/data/churn_prediction_metrics.json', 'w') as f:
        json.dump(metrics, f)
    
    return metrics

def run_clv_analysis():
    engine = create_engine(db_connection_string)
    metrics = {}
    
    # Load transaction data
    transactions = pd.read_sql('SELECT * FROM transactions', engine)
    
    # Data Cleaning
    transactions['spend'] = pd.to_numeric(transactions['spend'], errors='coerce')
    transactions['units'] = pd.to_numeric(transactions['units'], errors='coerce')
    transactions = transactions.dropna(subset=['hshd_num', 'spend', 'units'])
    
    # Feature Engineering
    data = transactions.groupby('hshd_num').agg({
        'spend': 'sum',
        'units': 'sum'
    }).reset_index()
    
    # Calculate metrics
    metrics['avg_clv'] = f"${data['spend'].mean():.2f}"
    
    # Train-Test Split
    from sklearn.model_selection import train_test_split
    X = data[['units']]
    y = data['spend']
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Model Training
    from xgboost import XGBRegressor
    from sklearn.metrics import mean_squared_error, r2_score
    model = XGBRegressor(objective='reg:squarederror', random_state=42)
    model.fit(X_train, y_train)
    
    # Prediction and Evaluation
    y_pred = model.predict(X_test)
    
    mse = mean_squared_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)
    
    metrics['mse'] = f"{mse:.2f}"
    metrics['r2_score'] = f"{r2:.2f}"
    
    # Visualization
    plt.figure(figsize=(10,8))
    plt.scatter(y_test, y_pred, alpha=0.7, color='royalblue')
    plt.plot([y_test.min(), y_test.max()], [y_test.min(), y_test.max()], 'r--', lw=2)
    plt.xlabel('Actual Spend (CLV)')
    plt.ylabel('Predicted Spend (CLV)')
    plt.title('Actual vs Predicted Customer Lifetime Value (CLV)')
    plt.grid(True)
    plt.tight_layout()
    plt.savefig('static/images/clv_analysis.png', dpi=300)
    plt.close()
    
    # Save metrics
    with open('static/data/clv_analysis_metrics.json', 'w') as f:
        json.dump(metrics, f)
    
    return metrics

if __name__ == "__main__":
    # Run all analyses
    basket_metrics = run_basket_analysis()
    churn_metrics = run_churn_prediction()
    clv_metrics = run_clv_analysis()
    
    print("Analysis complete. Results saved to static/images and static/data directories.")
    
    # Generate HTML file with dynamic content
    # NOTE: Double curly braces {{ }} are escaped to display as single braces in the HTML
    html_template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Retail Analytics Dashboard</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            margin: 0;
            padding: 0;
            background-color: #f8f9fa;
        }}
        .container {{
            width: 95%;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        header {{
            background-color: #052c65;
            color: white;
            padding: 20px 0;
            text-align: center;
            border-radius: 5px;
            margin-bottom: 30px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        h1 {{
            margin: 0;
        }}
        .dashboard-section {{
            background-color: white;
            border-radius: 8px;
            padding: 25px;
            margin-bottom: 30px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.08);
        }}
        h2 {{
            color: #052c65;
            border-bottom: 2px solid #e9ecef;
            padding-bottom: 10px;
            margin-top: 0;
        }}
        .chart-container {{
            width: 100%;
            height: auto;
            margin: 20px 0;
            border: 1px solid #e9ecef;
            border-radius: 5px;
            overflow: hidden;
        }}
        .chart-img {{
            width: 100%;
            height: auto;
            display: block;
        }}
        .metrics {{
            display: flex;
            justify-content: space-between;
            flex-wrap: wrap;
            margin: 15px 0;
        }}
        .metric-card {{
            background-color: #f8f9fa;
            border-radius: 5px;
            padding: 15px;
            width: 30%;
            margin-bottom: 15px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        .metric-title {{
            font-size: 14px;
            font-weight: 600;
            color: #6c757d;
            margin-bottom: 5px;
        }}
        .metric-value {{
            font-size: 24px;
            font-weight: 700;
            color: #052c65;
        }}
        footer {{
            text-align: center;
            margin-top: 20px;
            padding: 10px;
            font-size: 12px;
            color: #6c757d;
        }}
        @media (max-width: 768px) {{
            .metric-card {{
                width: 100%;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Retail Analytics Dashboard</h1>
        </header>
        
        <div class="dashboard-section">
            <h2>Basket Analysis</h2>
            <div class="metrics">
                <div class="metric-card">
                    <div class="metric-title">Model Accuracy</div>
                    <div class="metric-value">{model_accuracy}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">High Purchase Rate</div>
                    <div class="metric-value">{high_purchase_rate}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">Average Spend</div>
                    <div class="metric-value">{avg_spend}</div>
                </div>
            </div>
            <div class="chart-container">
                <img src="static/images/basket_analysis.png" alt="Spend vs Units Chart" class="chart-img" />
                <p style="text-align: center; font-style: italic; margin-top: 5px;">
                    Spend vs Units (colored by High Purchase) - Shows relationship between customer spending and units purchased
                </p>
            </div>
            <p>The scatter plot shows the relationship between spend amount and units purchased. Points are colored based on "high purchase" classification (greater than 3 units). Clusters indicate potential customer segments for targeted marketing.</p>
        </div>
        
        <div class="dashboard-section">
            <h2>Churn Prediction</h2>
            <div class="metrics">
                <div class="metric-card">
                    <div class="metric-title">Churn Rate</div>
                    <div class="metric-value">{churn_rate}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">Model Precision</div>
                    <div class="metric-value">{model_precision}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">At-Risk Households</div>
                    <div class="metric-value">{at_risk_households}</div>
                </div>
            </div>
            <div class="chart-container">
                <img src="static/images/churn_prediction.png" alt="Churn Risk Distribution" class="chart-img" />
                <p style="text-align: center; font-style: italic; margin-top: 5px;">
                    Churn Risk Distribution - Shows number of households with high vs. low churn risk
                </p>
            </div>
            <p>The bar chart displays the distribution of households at risk of churning vs those likely to remain. Churn risk is determined by a significant drop in spending (>50% decrease from month 7 to month 8). Predictive features include monthly spending patterns.</p>
        </div>
        
        <div class="dashboard-section">
            <h2>Customer Lifetime Value (CLV)</h2>
            <div class="metrics">
                <div class="metric-card">
                    <div class="metric-title">Avg CLV</div>
                    <div class="metric-value">{avg_clv}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">R² Score</div>
                    <div class="metric-value">{r2_score}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">MSE</div>
                    <div class="metric-value">{mse}</div>
                </div>
            </div>
            <div class="chart-container">
                <img src="static/images/clv_analysis.png" alt="Actual vs Predicted CLV" class="chart-img" />
                <p style="text-align: center; font-style: italic; margin-top: 5px;">
                    Actual vs Predicted Customer Lifetime Value - Shows model prediction accuracy
                </p>
            </div>
            <p>The scatter plot compares actual vs. predicted customer lifetime value (using total spend as a proxy). Points closer to the red diagonal line indicate more accurate predictions. The model uses total units purchased as the primary predictor of customer spending potential.</p>
        </div>
        
        <footer>
            <p>Retail Analytics Dashboard | Data Updated: {current_date}</p>
        </footer>
    </div>
</body>
</html>
"""
    
    # Create a dictionary with all the values needed for the template
    template_data = {
        'model_accuracy': basket_metrics.get('model_accuracy', 'N/A'),
        'high_purchase_rate': basket_metrics.get('high_purchase_rate', 'N/A'),
        'avg_spend': basket_metrics.get('avg_spend', 'N/A'),
        'churn_rate': churn_metrics.get('churn_rate', 'N/A'),
        'model_precision': churn_metrics.get('model_precision', 'N/A'),
        'at_risk_households': churn_metrics.get('at_risk_households', 'N/A'),
        'avg_clv': clv_metrics.get('avg_clv', 'N/A'),
        'r2_score': clv_metrics.get('r2_score', 'N/A'),
        'mse': clv_metrics.get('mse', 'N/A'),
        'current_date': pd.Timestamp.now().strftime('%B %d, %Y')
    }
    
    # Write the formatted HTML to file
    with open('Analytics.html', 'w') as f:
        f.write(html_template.format(**template_data))
    
    print("Analytics.html file generated successfully.")