import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('APCA_API_KEY_ID')
SECRET_KEY = os.getenv('APCA_API_SECRET_KEY')
BASE_URL = os.getenv('APCA_API_BASE_URL', 'https://paper-api.alpaca.markets')

BUY_THRESHOLDS = {'FFIE': 0.58, 'NXTC': 1.20, 'RGF': 0.65, 'PPSI': 3.70, 'MGRX': 0.41, 'CDXC': 3.20}
SELL_THRESHOLDS = {'FFIE': 0.5898, 'NXTC': 1.2110, 'RGF': 0.66, 'PPSI': 4.00, 'MGRX': 0.49, 'CDXC': 3.35}
SYMBOLS = ['FFIE', 'NXTC', 'RGF', 'PPSI', 'MGRX', 'CDXC']
STRATEGIES = ['Scalping', 'Momentum Trading', 'Breakout Trading', 'Reversal Trading', 'News-Based Trading']
