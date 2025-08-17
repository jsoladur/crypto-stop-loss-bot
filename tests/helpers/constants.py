from os import path

MAX_SECONDS = 15
BUY_SELL_SIGNALS_MOCK_FILES_PATH = path.realpath(
    path.join(path.dirname(path.abspath(__file__)), "resources", "buy_sell_signals_mock_files")
)
MOCK_CRYPTO_CURRENCIES = ["BTC", "ETH", "SOL", "SUI", "XRP"]
MOCK_SYMBOLS = [f"{crypto}/EUR" for crypto in MOCK_CRYPTO_CURRENCIES]
