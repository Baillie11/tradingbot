from flask import Blueprint, render_template, request, redirect, url_for
from config import BUY_THRESHOLDS, SELL_THRESHOLDS, SYMBOLS, STRATEGIES
from utils import get_stock_data, get_positions, get_market_status, get_portfolio_balance, get_buying_power, get_account_type
from jobs import check_trading_conditions, emit_data_updates
from apscheduler.schedulers.background import BackgroundScheduler

app = Blueprint('app', __name__)

selected_symbols = SYMBOLS.copy()
selected_strategy = 'Scalping'
broker = 'Alpaca'

# Initialize global variables
last_actions = {symbol: {'action': None, 'price': None} for symbol in SYMBOLS}
trade_records = []

@app.route('/')
def index():
    positions = get_positions()
    data_list = [get_stock_data(symbol, positions) for symbol in selected_symbols]
    market_status = get_market_status()
    portfolio_balance = get_portfolio_balance()
    buying_power = get_buying_power()
    account_type = get_account_type()
    return render_template('index.html', data_list=data_list, market_status=market_status, portfolio_balance=portfolio_balance, buying_power=buying_power, account_type=account_type, last_actions=last_actions, trade_records=trade_records)

@app.route('/about')
def about():
    version = "1.0.0"
    updates = [
        "Initial release with basic trading features",
        "Added support for custom stock selection",
        "Implemented various trading strategies"
    ]
    return render_template('about.html', version=version, updates=updates)

@app.route('/setup', methods=['GET', 'POST'])
def setup():
    global selected_symbols, BUY_THRESHOLDS, SELL_THRESHOLDS, broker, selected_strategy
    if request.method == 'POST':
        selected_symbols = request.form.getlist('symbols')
        selected_strategy = request.form['strategy']
        broker = request.form['broker']
        for symbol in selected_symbols:
            BUY_THRESHOLDS[symbol] = float(request.form[f'buy_{symbol}'])
            SELL_THRESHOLDS[symbol] = float(request.form[f'sell_{symbol}'])
        return redirect(url_for('app.index'))
    
    return render_template('setup.html', symbols=SYMBOLS, strategies=STRATEGIES, broker=broker, selected_symbols=selected_symbols, buy_thresholds=BUY_THRESHOLDS, sell_thresholds=SELL_THRESHOLDS, selected_strategy=selected_strategy)

def create_app(socketio, flask_app):
    @socketio.on('connect')
    def handle_connect():
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
        })

    flask_app.register_blueprint(app)

    scheduler = BackgroundScheduler()
    scheduler.add_job(func=check_trading_conditions, args=[socketio, selected_symbols], trigger="interval", minutes=1)
    scheduler.add_job(func=emit_data_updates, args=[socketio, selected_symbols], trigger="interval", seconds=30)
    scheduler.start()

    try:
        socketio.run(flask_app, host='0.0.0.0', port=5000, debug=True)
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        scheduler.shutdown()
