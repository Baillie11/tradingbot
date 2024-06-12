import os
import time
from flask import Flask, render_template
from flask_socketio import SocketIO
import alpaca_trade_api as tradeapi
from datetime import datetime, timedelta
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
import csv
import yfinance as yf
import logging

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
socketio = SocketIO(app)

API_KEY = os.getenv('APCA_API_KEY_ID')
SECRET_KEY = os.getenv('APCA_API_SECRET_KEY')
BASE_URL = os.getenv('APCA_API_BASE_URL', 'https://paper-api.alpaca.markets')

api = tradeapi.REST(API_KEY, SECRET_KEY, BASE_URL, api_version='v2')

# Configure logging
logging.basicConfig(level=logging.INFO)

def get_last_close_price(symbol):
    try:
        stock = yf.Ticker(symbol)
        hist = stock.history(period="5d")  # Fetch last 5 days to ensure we get the most recent closing price
        if not hist.empty:
            return round(hist['Close'].iloc[-1], 2)
        else:
            raise ValueError(f"No data available for {symbol}")
    except Exception as e:
        print(f"Error fetching last close price for {symbol} from Yahoo Finance: {e}")
        return None

# Define your trading strategy thresholds
BUY_THRESHOLDS = {'FFIE': .58, 'NXTC': 1.20, 'RGF': .65, 'PPSI': 3.70, 'MGRX':0.41, 'CDXC': 3.20}
SELL_THRESHOLDS = {'FFIE': .5898, 'NXTC': 1.2110, 'RGF': .66, 'PPSI':4.00, 'MGRX':0.49,'CDXC':3.35}
SYMBOLS = ['FFIE', 'NXTC', 'RGF', 'PPSI', 'MGRX','CDXC']

# Global variables to store the last action and trade records
last_actions = {symbol: {'action': None, 'price': None} for symbol in SYMBOLS}
trade_records = []

# File path for logging trades
trade_log_file = 'trades.csv'

def log_trade_to_file(trade, portfolio_balance):
    file_exists = os.path.isfile(trade_log_file)
    with open(trade_log_file, mode='a', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=['symbol', 'qty', 'side', 'price', 'time', 'portfolio_balance'])
        if not file_exists:
            writer.writeheader()
        trade['portfolio_balance'] = portfolio_balance
        writer.writerow(trade)

def get_account_type():
    if 'paper' in BASE_URL:
        return 'Paper'
    else:
        return 'Live'

def get_market_status():
    clock = api.get_clock()
    if clock.is_open:
        return 'Open'
    else:
        return 'Closed'

def get_portfolio_balance():
    account = api.get_account()
    return float(account.equity)

def get_buying_power():
    account = api.get_account()
    return float(account.buying_power)

def get_positions():
    try:
        positions = api.list_positions()
        return {position.symbol: int(position.qty) for position in positions}
    except Exception as e:
        print(f"Error getting positions: {e}")
        return {}

def get_stock_data(symbol, positions):
    clock = api.get_clock()
    if clock.is_open:
        try:
            trade = api.get_latest_trade(symbol)
            current_price = round(trade.price, 2)
            time = trade.timestamp
        except Exception as e:
            print(f"Error getting latest trade for {symbol}: {e}")
            current_price = None
            time = None
    else:
        try:
            current_price = get_last_close_price(symbol)
            time = datetime.now()
        except Exception as e:
            print(f"Error getting last close price for {symbol}: {e}")
            current_price = None
            time = None

    return {
        'symbol': symbol,
        'last_close': current_price,
        'last_close_time': time,
        'buy_threshold': BUY_THRESHOLDS[symbol],
        'sell_threshold': SELL_THRESHOLDS[symbol],
        'exchange': 'NASDAQ',
        'shares_owned': positions.get(symbol, 0)
    }

def place_order(symbol, qty, side, type='market', time_in_force='gtc'):
    global trade_records
    try:
        order = api.submit_order(
            symbol=symbol,
            qty=qty,
            side=side,
            type=type,
            time_in_force=time_in_force
        )
        logging.info(f"Order submitted: {order}")
        # Wait for the order to be filled
        retries = 3
        while retries > 0:
            order_status = api.get_order(order.id)
            if order_status.status == 'filled':
                break
            retries -= 1
            logging.warning(f"Order not filled, retrying... {retries} attempts left.")
            time.sleep(10)  # Wait for 3 seconds before retrying
        else:
            logging.error(f"Order {order.id} not filled after retries.")
            return None
        
        filled_avg_price = round(float(order_status.filled_avg_price), 2)
        trade = {
            'symbol': symbol,
            'qty': qty,
            'side': side,
            'price': filled_avg_price,
            'time': order_status.filled_at
        }
        portfolio_balance = get_portfolio_balance()
        trade_records.append(trade)
        log_trade_to_file(trade, portfolio_balance)
        return order
    except Exception as e:
        logging.error(f"Error placing order: {e}")
        return None

def check_trading_conditions():
    global last_actions
    clock = api.get_clock()
    
    # Check if the market is open
    if not clock.is_open:
        logging.info("Market is closed. No trading will be done.")
        return
    
    for symbol in SYMBOLS:
        stock_data = get_stock_data(symbol)
        current_price = stock_data['last_close']
        if current_price:
            if current_price < BUY_THRESHOLDS[symbol]:
                logging.info(f"Current price {current_price} is below buy threshold for {symbol}. Buying.")
                order = place_order(symbol, 1, 'buy')
            elif current_price > SELL_THRESHOLDS[symbol]:
                logging.info(f"Current price {current_price} is above sell threshold for {symbol}. Selling.")
                order = place_order(symbol, 1, 'sell')
        else:
            logging.warning(f"No current price available to evaluate trading conditions for {symbol}.")

def emit_data_updates():
    positions = get_positions()
    data_list = [get_stock_data(symbol, positions) for symbol in SYMBOLS]
    market_status = get_market_status()
    portfolio_balance = get_portfolio_balance()
    buying_power = get_buying_power()
    account_type = get_account_type()
    socketio.emit('data_update', {
        'data_list': data_list,
        'market_status': market_status,
        'portfolio_balance': portfolio_balance,
        'buying_power': buying_power,
        'account_type': account_type,
        'last_actions': last_actions,
        'trade_records': trade_records
    }, namespace='/')

@app.route('/')
def index():
    positions = get_positions()
    data_list = [get_stock_data(symbol, positions) for symbol in SYMBOLS]
    market_status = get_market_status()
    portfolio_balance = get_portfolio_balance()
    buying_power = get_buying_power()
    account_type = get_account_type()
    return render_template('index.html', data_list=data_list, market_status=market_status, portfolio_balance=portfolio_balance, buying_power=buying_power, account_type=account_type, last_actions=last_actions, trade_records=trade_records)

@socketio.on('connect')
def handle_connect():
    positions = get_positions()
    data_list = [get_stock_data(symbol, positions) for symbol in SYMBOLS]
    market_status = get_market_status()
    portfolio_balance = get_portfolio_balance()
    buying_power = get_buying_power()
    account_type = get_account_type()
    socketio.emit('data_update', {
        'data_list': data_list,
        'market_status': market_status,
        'portfolio_balance': portfolio_balance,
        'buying_power': buying_power,
        'account_type': account_type,
        'last_actions': last_actions,
        'trade_records': trade_records
    })

if __name__ == '__main__':
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=check_trading_conditions, trigger="interval", minutes=1)
    scheduler.add_job(func=emit_data_updates, trigger="interval", seconds=30)  # Emit data updates every 30 seconds
    scheduler.start()
    try:
        socketio.run(app, host='0.0.0.0', port=5000, debug=True)
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        scheduler.shutdown()
