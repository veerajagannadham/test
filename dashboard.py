import dash
from dash import dcc, html
import pandas as pd
from sqlalchemy import create_engine

# Connect to database
db_connection_string = 'mysql+pymysql://root:IamGOD%402002@localhost:3307/retail_db'
engine = create_engine(db_connection_string)

# Read transactions data
df = pd.read_sql('SELECT * FROM transactions', engine)

# Create Dash app
app = dash.Dash(__name__)

app.layout = html.Div([
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
                'yaxis': {'title': 'Total Spend'}
            }
        }
    )
])

if __name__ == '__main__':
    app.run_server(debug=True)