import pandas as pd
from sqlalchemy import create_engine
import os
from datetime import datetime

# Database connection configuration
DB_CONFIG = {
    'user': 'root',
    'password': 'admin',
    'host': '127.0.0.1',
    'database': 'azure_retail',
    'port': 3306
}

def clean_data(df):
    """Clean and standardize column names"""
    df.columns = [col.strip().lower() for col in df.columns]
    return df

def load_data():
    try:
        # Create database connection
        connection_string = f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
        engine = create_engine(connection_string)
        
        # Load and clean data files
        print("Loading data files...")
        
        # Load households data
        households = pd.read_csv('data/400_households.csv')
        households = clean_data(households)
        print(f"Loaded {len(households)} household records")
        
        # Load transactions data (limiting to 400 records as per filename)
        transactions = pd.read_csv('data/400_transactions.csv')
        transactions = clean_data(transactions)
        print(f"Loaded {len(transactions)} transaction records")
        
        # Load products data if available
        try:
            products = pd.read_csv('data/400_products.csv')
            products = clean_data(products)
            print(f"Loaded {len(products)} product records")
        except FileNotFoundError:
            print("Products file not found, skipping")
            products = None
        
        # Upload data to database
        print("Uploading data to database...")
        
        # Households table
        households.to_sql('households', engine, if_exists='replace', index=False)
        print("Uploaded households data")
        
        # Transactions table
        transactions.to_sql('transactions', engine, if_exists='replace', index=False)
        print("Uploaded transactions data")
        
        # Products table if available
        if products is not None:
            products.to_sql('products', engine, if_exists='replace', index=False)
            print("Uploaded products data")
        
        print("Data loading completed successfully!")
        
    except Exception as e:
        print(f"Error loading data: {str(e)}")
        raise

if __name__ == "__main__":
    load_data()