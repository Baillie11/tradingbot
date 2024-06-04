import os
from flask import Flask, render_template
from flask_socketio import SocketIO
import alpaca_trade_api as tradeapi
from datetime import datetime, timedelta
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
import csv
import yfinance as yf

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
socketio = SocketIO(app)

API_KEY = os.getenv('APCA_API_KEY_ID')
SECRET_KEY = os.getenv('APCA_API_SECRET_KEY')
BASE_URL = os.getenv('APCA_API_BASE_URL', 'https://paper-api.alpaca.markets')

api = tradeapi.REST(API_KEY, SECRET_KEY, BASE_URL, api_version='v2')

def get_last_close_price(symbol):
    stock = yf.Ticker(symbol)
    hist = stock.history(period="1d")
    if not hist.empty:
        return hist['Close'][0]
    else:
        raise ValueError(f"No data available for {symbol}")

# Define your trading strategy thresholds
BUY_THRESHOLDS = {'AAPL': 192.00, 'TSLA': 177.00, 'GLD':215.00}
SELL_THRESHOLDS = {'AAPL': 194.00, 'TSLA': 180.00, 'GLD': 218.00}
SYMBOLS = ['AAPL', 'TSLA', 'GLD']

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

def get_stock_data(symbol):
    clock = api.get_clock()
    if clock.is_open:
        try:
            trade = api.get_latest_trade(symbol)
            current_price = trade.price
            time = trade.timestamp
        except Exception as e:
            print(f"Error getting latest trade for {symbol}: {e}")
            current_price = None
            time = None
    else:
        today = datetime.today().date()
        yesterday = today - timedelta(days=1)
        try:
            bars = api.get_bars(symbol, tradeapi.rest.TimeFrame.Day, start=yesterday.isoformat(), end=today.isoformat()).df
            if not bars.empty:
                current_price = bars.iloc[-1]['close']
                time = bars.index[-1]
            else:
                current_price = None
                time = None
        except Exception as e:
            print(f"Error getting bars for {symbol}: {e}")
            current_price = None
            time = None

    return {
        'symbol': symbol,
        'last_close': current_price,
        'last_close_time': time,
        'exchange': 'NASDAQ'
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
        print(f"Order submitted: {order}")
        # Wait for the order to be filled
        while True:
            order_status = api.get_order(order.id)
            if order_status.status == 'filled':
                break
        filled_avg_price = float(order_status.filled_avg_price)
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
        print(f"Error placing order: {e}")
        return None

def check_trading_conditions():
    global last_actions
    for symbol in SYMBOLS:
        stock_data = get_stock_data(symbol)
        current_price = stock_data['last_close']
        if current_price:
            if current_price < BUY_THRESHOLDS[symbol]:
                print(f"Current price {current_price} is below buy threshold for {symbol}. Buying.")
                order = place_order(symbol, 1, 'buy')
                if order:
                    last_actions[symbol] = {'action': 'Bought', 'price': current_price}
                    socketio.emit('trade_update', {'symbol': symbol, 'last_action': last_actions[symbol], 'trade_records': trade_records}, broadcast=True)
            elif current_price > SELL_THRESHOLDS[symbol]:
                print(f"Current price {current_price} is above sell threshold for {symbol}. Selling.")
                order = place_order(symbol, 1, 'sell')
                if order:
                    last_actions[symbol] = {'action': 'Sold', 'price': current_price}
                    socketio.emit('trade_update', {'symbol': symbol, 'last_action': last_actions[symbol], 'trade_records': trade_records}, broadcast=True)
        else:
            print(f"No current price available to evaluate trading conditions for {symbol}.")

def emit_data_updates():
    data_list = [get_stock_data(symbol) for symbol in SYMBOLS]
    market_status = get_market_status()
    portfolio_balance = get_portfolio_balance()
    account_type = get_account_type()
    socketio.emit('data_update', {
        'data_list': data_list,
        'market_status': market_status,
        'portfolio_balance': portfolio_balance,
        'account_type': account_type,
        'last_actions': last_actions,
        'trade_records': trade_records
    }, namespace='/')

@app.route('/')
def index():
    data_list = [get_stock_data(symbol) for symbol in SYMBOLS]
    market_status = get_market_status()
    portfolio_balance = get_portfolio_balance()
    account_type = get_account_type()
    return render_template('index.html', data_list=data_list, market_status=market_status, portfolio_balance=portfolio_balance, account_type=account_type, last_actions=last_actions, trade_records=trade_records)

@socketio.on('connect')
def handle_connect():
    data_list = [get_stock_data(symbol) for symbol in SYMBOLS]
    market_status = get_market_status()
    portfolio_balance = get_portfolio_balance()
    account_type = get_account_type()
    socketio.emit('data_update', {
        'data_list': data_list,
        'market_status': market_status,
        'portfolio_balance': portfolio_balance,
        'account_type': account_type,
        'last_actions': last_actions,
        'trade_records': trade_records
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=check_trading_conditions, trigger="interval", minutes=1)
    scheduler.add_job(func=emit_data_updates, trigger="interval", seconds=30)  # Emit data updates every 30 seconds
    scheduler.start()
    try:
        socketio.run(app, debug=True)
        app.run(host='0.0.0.0', port=5000, debug=True)
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        scheduler.shutdown()
