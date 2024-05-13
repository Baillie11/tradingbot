from flask import Flask, render_template
from alpaca_trade_api import REST, TimeFrame
import os
from dotenv import load_dotenv
import pandas as pd
import logging

app = Flask(__name__)

# Configure logging
logging.basicConfig(filename='app.log', level=logging.DEBUG,
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

@app.route('/')
def index():
    symbols = ['GLD', 'AAPL', 'MSFT']  # List of symbols you want to report on
    data_list = []
    clock = api.get_clock()
    market_status = 'Open' if clock.is_open else 'Closed'
    check_again_message = None

    if not clock.is_open:
        check_again_message = "Market is closed. Will check again in 1 hour."
        logger.info("Market is closed.")

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
                           market_status=market_status, check_again_message=check_again_message)

if __name__ == '__main__':
    app.run(debug=True)
