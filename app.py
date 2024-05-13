from flask import Flask, render_template
from apscheduler.schedulers.background import BackgroundScheduler
import datetime
import pytz
from alpaca_trade_api import REST, TimeFrame
import os
from dotenv import load_dotenv
import pandas as pd
import logging
import time

app = Flask(__name__)

if not os.path.exists('logs'):
    os.makedirs('logs')

# Configure logging
logging.basicConfig(filename='logs/app.log', level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Alpaca API credentials
API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('API_SECRET')
BASE_URL = 'https://paper-api.alpaca.markets'

# Initialize Alpaca API
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
    """Execute trades based on the given signals."""
    for signal in signals:
        if signal['action'] == 'buy':
            api.submit_order(
                symbol=signal['symbol'],
                qty=1,
                side='buy',
                type='market',
                time_in_force='gtc'
            )
        elif signal['action'] == 'sell':
            api.submit_order(
                symbol=signal['symbol'],
                qty=1,
                side='sell',
                type='market',
                time_in_force='gtc'
            )

def is_market_open():
    ny_time = datetime.datetime.now(pytz.timezone('America/New_York'))
    weekday = ny_time.weekday()
    current_time = ny_time.time()
    market_start = datetime.time(9, 30, 0)
    market_end = datetime.time(16, 0, 0)

    if weekday >= 5:  # Market is closed on weekends
        return False, market_start

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

@app.route('/')
def index():
    symbols = ['GLD', 'AAPL', 'MSFT']
    data_list = []
    clock = api.get_clock()
    market_status = 'Open' if clock.is_open else 'Closed'
    countdown_message = get_market_open_countdown() if not clock.is_open else None

    if not clock.is_open:
        check_again_message = "Market is closed. Will check again when it opens."
        logger.info("Market is closed.")
    else:
        check_again_message = None

    account = api.get_account()
    portfolio_balance = account.equity
    logger.debug(f"Current portfolio balance: {portfolio_balance}")

    for symbol in symbols:
        try:
            bars = api.get_bars(symbol, TimeFrame.Day, limit=5, adjustment='raw').df
            exchange = api.get_asset(symbol).exchange

            if not bars.empty:
                last_close = bars['close'].iloc[-1]
                last_close_time = pd.to_datetime(bars.index[-1])
                sma = calculate_sma(bars['close']).iloc[-1]
                data_list.append({
                    'symbol': symbol,
                    'last_close': last_close,
                    'last_close_time': last_close_time,
                    'sma': sma,
                    'market_status': market_status,
                    'exchange': exchange
                })
            else:
                data_list.append({'symbol': symbol, 'message': 'No recent close data available'})

        except Exception as e:
            logger.error(f"Error retrieving data for {symbol}: {e}")
            data_list.append({'symbol': symbol, 'message': str(e)})

    trading_signals = evaluate_trading_signals(data_list)
    execute_trades(trading_signals)

    return render_template('index.html', data_list=data_list, portfolio_balance=portfolio_balance,
                           market_status=market_status, check_again_message=check_again_message,
                           countdown_message=countdown_message)

if __name__ == '__main__':
    scheduler.start()
    app.run(debug=True)
