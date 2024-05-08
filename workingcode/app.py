from flask import Flask, render_template
import os
from alpaca_trade_api import REST, TimeFrame
from dotenv import load_dotenv

app = Flask(__name__)

# Load environment variables
load_dotenv()

# Alpaca API credentials
API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('API_SECRET')
BASE_URL = 'https://paper-api.alpaca.markets'  # Use the paper trading URL

# Initialize Alpaca API
api = REST(API_KEY, API_SECRET, BASE_URL, api_version='v2')

@app.route('/')
def index():
    symbol = 'GLD'
    # Make sure to use TimeFrame.Day directly since it's already imported
    bars = api.get_bars(symbol, TimeFrame.Day, limit=1).df
    if not bars.empty:
        last_close = bars['close'].iloc[-1]
        last_close_time = bars.index[-1]
        data = {'symbol': symbol, 'last_close': last_close, 'last_close_time': last_close_time}
    else:
        data = {'symbol': symbol, 'message': 'No data available'}
    return render_template('index.html', data=data)

if __name__ == '__main__':
    app.run(debug=True)
