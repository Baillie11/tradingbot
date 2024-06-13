import yfinance as yf
import alpaca_trade_api as tradeapi
from datetime import datetime
import csv
import os
import logging
from config import API_KEY, SECRET_KEY, BASE_URL, BUY_THRESHOLDS, SELL_THRESHOLDS

# Initialize Alpaca API
api = tradeapi.REST(API_KEY, SECRET_KEY, BASE_URL, api_version='v2')

def get_last_close_price(symbol):
    try:
        stock = yf.Ticker(symbol)
        hist = stock.history(period="5d")
        if not hist.empty:
            return round(hist['Close'].iloc[-1], 2)
        else:
            raise ValueError(f"No data available for {symbol}")
    except Exception as e:
        logging.error(f"Error fetching last close price for {symbol} from Yahoo Finance: {e}")
        return None

def get_stock_data(symbol, positions):
    clock = api.get_clock()
    if clock.is_open:
        try:
            trade = api.get_latest_trade(symbol)
            current_price = round(trade.price, 2)
            time = trade.timestamp
        except Exception as e:
            logging.error(f"Error getting latest trade for {symbol}: {e}")
            current_price = None
            time = None
    else:
        try:
            current_price = get_last_close_price(symbol)
            time = datetime.now()
        except Exception as e:
            logging.error(f"Error getting last close price for {symbol}: {e}")
            current_price = None
            time = None

    shares_owned = positions.get(symbol, 0)
    value_in_dollars = round(current_price * shares_owned, 2) if current_price else 0

    return {
        'symbol': symbol,
        'current_price': current_price,
        'last_close_time': time,
        'buy_threshold': BUY_THRESHOLDS[symbol],
        'sell_threshold': SELL_THRESHOLDS[symbol],
        'exchange': 'NASDAQ',
        'shares_owned': shares_owned,
        'value_in_dollars': value_in_dollars
    }

def log_trade_to_file(trade, portfolio_balance, trade_log_file='trades.csv'):
    file_exists = os.path.isfile(trade_log_file)
    with open(trade_log_file, mode='a', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=['symbol', 'qty', 'side', 'price', 'time', 'portfolio_balance'])
        if not file_exists:
            writer.writeheader()
        trade['portfolio_balance'] = portfolio_balance
        writer.writerow(trade)

def get_positions():
    try:
        positions = api.list_positions()
        return {position.symbol: int(position.qty) for position in positions}
    except Exception as e:
        logging.error(f"Error getting positions: {e}")
        return {}

def get_portfolio_balance():
    account = api.get_account()
    return float(account.equity)

def get_buying_power():
    account = api.get_account()
    return float(account.buying_power)

def get_market_status():
    clock = api.get_clock()
    return 'Open' if clock.is_open else 'Closed'

def get_account_type():
    return 'Paper' if 'paper' in BASE_URL else 'Live'

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
        retries = 3
        while retries > 0:
            order_status = api.get_order(order.id)
            if order_status.status == 'filled':
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

                # Emit the updated trade and last action
                last_actions[symbol] = {'action': side.capitalize(), 'price': filled_avg_price}
                socketio.emit('trade_update', {'symbol': symbol, 'last_action': last_actions[symbol], 'trade_records': trade_records}, broadcast=True)
                return order

            # Check if the order is canceled or rejected
            if order_status.status in ['canceled', 'rejected']:
                logging.error(f"Order {order.id} was {order_status.status}: {order_status}")
                return None

            retries -= 1
            logging.warning(f"Order not filled, retrying... {retries} attempts left.")
            time.sleep(3)  # Wait for 3 seconds before retrying

        logging.error(f"Order {order.id} not filled after retries.")
        return None
    except Exception as e:
        logging.error(f"Error placing order: {e}")
        return None
