from crypto_trailing_stop.commons.constants import TRADE_NOW_DEFAULT_TOTAL_CAPITAL
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange import AbstractOperatingExchangeService
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.vo import PortfolioBalance
from crypto_trailing_stop.infrastructure.services.auto_buy_trader_config_service import AutoBuyTraderConfigService
from crypto_trailing_stop.infrastructure.services.buy_sell_signals_config_service import BuySellSignalsConfigService
from crypto_trailing_stop.infrastructure.services.crypto_analytics_service import CryptoAnalyticsService
from crypto_trailing_stop.infrastructure.services.orders_analytics_service import OrdersAnalyticsService
from crypto_trailing_stop.infrastructure.services.vo.trade_now_hints import LeveragedPositionHints, TradeNowHints


class TradeNowHintsService:
    def __init__(
        self,
        buy_sell_signals_config_service: BuySellSignalsConfigService,
        auto_buy_trader_config_service: AutoBuyTraderConfigService,
        operating_exchange_service: AbstractOperatingExchangeService,
        crypto_analytics_service: CryptoAnalyticsService,
        orders_analytics_service: OrdersAnalyticsService,
    ) -> None:
        self._buy_sell_signals_config_service = buy_sell_signals_config_service
        self._auto_buy_trader_config_service = auto_buy_trader_config_service
        self._operating_exchange_service = operating_exchange_service
        self._crypto_analytics_service = crypto_analytics_service
        self._orders_analytics_service = orders_analytics_service

    async def get_trade_now_hints(self, symbol: str, leverage_value: int) -> TradeNowHints:
        async with await self._operating_exchange_service.get_client() as client:
            account_info = await self._operating_exchange_service.get_account_info(client=client)
            porfolio_balance = await self._operating_exchange_service.retrieve_porfolio_balance(
                account_info.currency_code, client=client
            )
            porfolio_balance = (
                porfolio_balance
                if porfolio_balance.total_balance > 0
                else PortfolioBalance(total_balance=TRADE_NOW_DEFAULT_TOTAL_CAPITAL)
            )
            crypto_currency, symbol = symbol, f"{symbol}/{account_info.currency_code}"

            auto_buy_trader_config = await self._auto_buy_trader_config_service.find_by_symbol(crypto_currency)
            fiat_wallet_percent_assigned = (
                auto_buy_trader_config.fiat_wallet_percent_assigned
                if auto_buy_trader_config.fiat_wallet_percent_assigned > 0
                else 100
            )

            buy_sell_signals_config = await self._buy_sell_signals_config_service.find_by_symbol(crypto_currency)
            trading_market_config = await self._operating_exchange_service.get_trading_market_config_by_symbol(
                symbol, client=client
            )
            tickers = await self._operating_exchange_service.get_single_tickers_by_symbol(symbol, client=client)
            crypto_market_metrics = await self._crypto_analytics_service.get_crypto_market_metrics(
                symbol, client=client
            )
            suggested_stop_loss_percent_value = (
                self._orders_analytics_service.calculate_suggested_stop_loss_percent_value(
                    avg_buy_price=tickers.ask_or_close,
                    buy_sell_signals_config=buy_sell_signals_config,
                    last_candle_market_metrics=crypto_market_metrics,
                    trading_market_config=trading_market_config,
                )
            )
            *_, suggested_take_profit_percent_value = self._orders_analytics_service.calculate_take_profit_limit_price(
                buy_price=tickers.ask_or_close,
                stop_loss_percent_value=suggested_stop_loss_percent_value,
                buy_sell_signals_config=buy_sell_signals_config,
                trading_market_config=trading_market_config,
            )
            # 3. Calculate Risk Metrics (based on your inputs)
            capital_to_use_as_margin = porfolio_balance.total_balance * (fiat_wallet_percent_assigned / 100)
            position_size_nocional = capital_to_use_as_margin * leverage_value

            # 4. Calculate Hints for LONG
            long_metrics = self._calculate_position_metrics(
                entry_price=tickers.ask,  # You buy at the 'ask' price
                stop_loss_percent=suggested_stop_loss_percent_value,
                take_profit_percent=suggested_take_profit_percent_value,
                position_size_nocional=position_size_nocional,
                required_margin=capital_to_use_as_margin,
                total_capital=porfolio_balance.total_balance,
                leverage=leverage_value,
                is_short_position=False,
            )

            # 5. Calculate Hints for SHORT
            short_metrics = self._calculate_position_metrics(
                entry_price=tickers.bid,  # You sell at the 'bid' price
                stop_loss_percent=suggested_stop_loss_percent_value,
                take_profit_percent=suggested_take_profit_percent_value,
                position_size_nocional=position_size_nocional,
                required_margin=capital_to_use_as_margin,
                total_capital=porfolio_balance.total_balance,
                leverage=leverage_value,
                is_short_position=True,
            )
            # 6. Return the complete hints object
            ret = TradeNowHints(
                symbol=symbol,
                leverage_value=leverage_value,
                tickers=tickers,
                crypto_market_metrics=crypto_market_metrics,
                fiat_wallet_percent_assigned=fiat_wallet_percent_assigned,
                stop_loss_percent_value=suggested_stop_loss_percent_value,
                take_profit_percent_value=suggested_take_profit_percent_value,
                profit_factor=round(suggested_take_profit_percent_value / suggested_stop_loss_percent_value, ndigits=2),
                long=long_metrics,
                short=short_metrics,
            )
            return ret

    def _calculate_position_metrics(
        self,
        entry_price: float,
        stop_loss_percent: float,
        take_profit_percent: float,
        position_size_nocional: float,
        required_margin: float,
        total_capital: float,
        leverage: int,
        *,
        is_short_position: bool = False,
    ) -> LeveragedPositionHints:
        """
        Helper function that calculates all risk metrics for one direction (Long or Short).
        """
        sl_percent_decimal = stop_loss_percent / 100
        tp_percent_decimal = take_profit_percent / 100
        # Liquidation is ~100% / leverage (e.g., 1 / 20x = 0.05 or 5%)
        liquidation_percent_decimal = 1 / leverage
        if is_short_position:  # Short
            # Price Calculations
            stop_loss_price = entry_price * (1 + sl_percent_decimal)
            take_profit_price = entry_price * (1 - tp_percent_decimal)
            liquidation_price = entry_price * (1 + liquidation_percent_decimal)
            # Safety Check
            is_safe = stop_loss_price < liquidation_price
        else:
            # Price Calculations
            stop_loss_price = entry_price * (1 - sl_percent_decimal)
            take_profit_price = entry_price * (1 + tp_percent_decimal)
            liquidation_price = entry_price * (1 - liquidation_percent_decimal)
            # Safety Check
            is_safe = stop_loss_price > liquidation_price

        # Risk Calculations (same for long and short)
        loss_at_stop_loss = position_size_nocional * sl_percent_decimal
        profit_at_stop_loss = position_size_nocional * tp_percent_decimal
        risk_as_percent_of_total_capital = (loss_at_stop_loss / total_capital) * 100

        return LeveragedPositionHints(
            position_type="Short" if is_short_position else "Long",
            entry_price=entry_price,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            required_margin=required_margin,
            position_size=position_size_nocional,
            loss_at_stop_loss=loss_at_stop_loss,
            profit_at_stop_loss=profit_at_stop_loss,
            risk_as_percent_of_total_capital=risk_as_percent_of_total_capital,
            liquidation_price=liquidation_price,
            is_safe_from_liquidation=is_safe,
        )
