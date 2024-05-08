from flask import Flask, render_template
from alpaca_trade_api import REST, TimeFrame
import os
from dotenv import load_dotenv

app = Flask(__name__)

# Load environment variables
load_dotenv()

# Alpaca API credentials
API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('API_SECRET')
BASE_URL = 'https://paper-api.alpaca.markets'

# Initialize Alpaca API
api = REST(API_KEY, API_SECRET, BASE_URL, api_version='v2')

@app.route('/')
def index():
    symbol = 'GLD'
    try:
        # Get the latest bar for the symbol
        bars = api.get_bars(symbol, TimeFrame.Day, limit=1).df
        market_status = 'Open' if api.get_clock().is_open else 'Closed'  # Market status
        exchange = api.get_asset(symbol).exchange  # Get marketplace name

        if not bars.empty:
            last_close = bars['close'].iloc[-1]
            last_close_time = bars.index[-1]
            data = {
                'symbol': symbol,
                'last_close': last_close,
                'last_close_time': last_close_time,
                'market_status': market_status,
                'exchange': exchange
            }
        else:
            data = {'symbol': symbol, 'message': 'No data available'}

    except Exception as e:
        data = {'symbol': symbol, 'message': str(e)}

    return render_template('index.html', data=data)

if __name__ == '__main__':
    app.run(debug=True)
