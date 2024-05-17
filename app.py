from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import datetime
import pytz
from alpaca_trade_api import REST, TimeFrame
import os
from dotenv import load_dotenv
import pandas as pd
import logging
import threading
import time  # Import time module
from apscheduler.schedulers.background import BackgroundScheduler  # Import BackgroundScheduler

# Initialize Flask and SocketIO
app = Flask(__name__)
socketio = SocketIO(app)

if not os.path.exists('logs'):
    os.makedirs('logs')

# Configure logging
logging.basicConfig(filename='logs/app.log', level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
logging.basicConfig(filename='logs/app.log', level=logging.DEBUG, format='%(asctime)s %(levelname)s %(name)s %(message)s')

# Initialize API and other necessary setups
API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('API_SECRET')
BASE_URL = os.getenv('BASE_URL')
api = REST(API_KEY, API_SECRET, BASE_URL, api_version='v2')

def get_market_open_countdown():
    timezone = pytz.timezone('America/New_York')
    now = datetime.datetime.now(timezone)
    next_open_date = now.date() + datetime.timedelta(days=1 if now.time() > datetime.time(16, 0) else 0)
    next_open_datetime = datetime.datetime.combine(next_open_date, datetime.time(9, 30))
    next_open_datetime = timezone.localize(next_open_datetime)  # Ensure the datetime is offset-aware
    countdown = next_open_datetime - now
    if countdown.days < 0:
        countdown = datetime.timedelta(seconds=0)  # Reset the countdown to zero if it's negative
    return str(countdown)

def calculate_sma(prices, window=5):
    """Calculate the Simple Moving Average for the given price series and window."""
    return prices.rolling(window=window).mean()

def evaluate_trading_signals(data):
    """Evaluate trading signals based on the trading logic."""
    signals = []
    for item in data:
        if 'last_close' in item and 'sma' in item:
            if item['last_close'] > item['sma']:
                signals.append({'symbol': item['symbol'], 'action': 'buy'})
            elif item['last_close'] < item['sma']:
                signals.append({'symbol': item['symbol'], 'action': 'sell'})
    return signals

def execute_trades(signals):
    """Execute trades based on the signals."""
    for signal in signals:
        symbol = signal['symbol']
        action = signal['action']
        # Implement your trade execution logic here
        print(f"Executing {action} for {symbol}")

def is_market_open():
    timezone = pytz.timezone('America/New_York')
    now = datetime.datetime.now(timezone)
    current_time = now.time()
    market_start = datetime.time(9, 30)
    market_end = datetime.time(16, 0)

    if market_start <= current_time <= market_end:
        return True, None
    elif current_time < market_start:
        return False, market_start
    else:
        return False, market_start  # Market closed, return next day's opening time

def wait_until_market_open():
    market_open, opening_time = is_market_open()
    while not market_open:
        now = datetime.datetime.now(pytz.timezone('America/New_York'))
        countdown = datetime.datetime.combine(now.date(), opening_time) - now
        if countdown.days < 0:
            countdown = datetime.datetime.combine(now.date() + datetime.timedelta(days=1), opening_time) - now
        hours, remainder = divmod(countdown.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        print(f"Market opens in {hours} hours, {minutes} minutes, and {seconds} seconds.")
        time.sleep(60)  # Sleep for 1 minute and check again
        market_open, _ = is_market_open()
    print("Market is now open!")

scheduler = BackgroundScheduler()
scheduler.add_job(wait_until_market_open, 'interval', minutes=60)
scheduler.start()

# Placeholder function for fetching stock data
def get_stock_data():
    symbols = ['GLD', 'AAPL', 'MSFT']
    end_date = datetime.datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.datetime.now() - datetime.timedelta(days=10)).strftime('%Y-%m-%d')
    data = []

    for symbol in symbols:
        barset = api.get_barset(symbol, TimeFrame.Day, start=start_date, end=end_date)
        bars = barset[symbol]
        for bar in bars:
            data.append({
                'symbol': symbol,
                'time': bar.t.isoformat(),
                'close': bar.c
            })

    return data

# Placeholder function for fetching portfolio balance
def get_portfolio_balance():
    try:
        # Fetch account information from Alpaca API
        account = api.get_account()

        # Extract portfolio balance
        portfolio_balance = float(account.equity)
        print(portfolio_balance)

        return portfolio_balance
    except Exception as e:
        logger.error(f"Error fetching portfolio balance: {e}")
        return 0


# Function to handle data fetching and trading
def fetch_and_trade():
    while True:
        if is_market_open():
            # Fetch data and evaluate signals
            data_list = get_stock_data()  # You will implement this to fetch and process stock data
            trading_signals = evaluate_trading_signals(data_list)
            execute_trades(trading_signals)
            # Emit update to the frontend
            socketio.emit('data_update', {'data_list': data_list, 'portfolio_balance': get_portfolio_balance()})
            
        socketio.sleep(60)  # Adjust time as needed

# Start the background thread
@socketio.on('connect')
def on_connect():
    threading.Thread(target=fetch_and_trade).start()
    emit('status', {'data': 'Connected'})

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    socketio.run(app, debug=True)
