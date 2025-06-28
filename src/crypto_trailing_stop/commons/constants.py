TRAILING_STOP_LOSS_DEFAULT_PERCENT = (
    2.50  # Best Spot Loss value intra-day, based on experience
)
TRAILING_STOP_LOSS_PRICE_DECREASE_THRESHOLD = 0.00025
NUMBER_OF_DECIMALS_IN_PRICE_BY_SYMBOL = {
    "BTC/EUR": 1,
    "XRP/EUR": 4,
}
DEFAULT_NUMBER_OF_DECIMALS_IN_PRICE = 2
AUTHORIZED_GOOGLE_USER_EMAILS = [
    "josemaria.sola.duran@gmail.com",
    "jmsola3092@gmail.com",
]
DEFAULT_IN_MEMORY_CACHE_TTL_IN_SECONDS = 86_400  # 1 day
BUY_SELL_MINUTES_PAST_HOUR_EXECUTION_CRON_PATTERN = [
    2,
    3,
    5,
    7,
    10,
    15,
    20,
    25,
    30,
    35,
    40,
    45,
    50,
    55,
]
BUY_SELL_ALERTS_TIMEFRAMES = ["4h", "1h"]
