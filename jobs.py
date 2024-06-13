import logging
from config import BUY_THRESHOLDS, SELL_THRESHOLDS, SYMBOLS
from utils import api, get_stock_data, get_positions, place_order, get_market_status, get_portfolio_balance, get_buying_power, get_account_type, log_trade_to_file

last_actions = {symbol: {'action': None, 'price': None} for symbol in SYMBOLS}
trade_records = []

def check_trading_conditions(socketio, selected_symbols):
    global last_actions
    clock = api.get_clock()
    
    if not clock.is_open:
        logging.info("Market is closed. No trading will be done.")
        return

    for symbol in selected_symbols:
        stock_data = get_stock_data(symbol, get_positions())
        current_price = stock_data['current_price']
        
        logging.info(f"Checking conditions for {symbol}:")
        logging.info(f"  Current price: {current_price}")
        logging.info(f"  Buy threshold: {BUY_THRESHOLDS[symbol]}")
        logging.info(f"  Sell threshold: {SELL_THRESHOLDS[symbol]}")

        if current_price:
            if current_price < BUY_THRESHOLDS[symbol]:
                logging.info(f"Current price {current_price} is below buy threshold for {symbol}. Buying.")
                order = place_order(symbol, 1, 'buy')
            elif current_price > SELL_THRESHOLDS[symbol]:
                logging.info(f"Current price {current_price} is above sell threshold for {symbol}. Selling.")
                order = place_order(symbol, 1, 'sell')
        else:
            logging.warning(f"No current price available to evaluate trading conditions for {symbol}.")

def emit_data_updates(socketio, selected_symbols):
    positions = get_positions()
    data_list = [get_stock_data(symbol, positions) for symbol in selected_symbols]
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
