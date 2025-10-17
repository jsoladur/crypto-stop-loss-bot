from aiogram import F
from aiogram.types import KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram3_form import Form, FormField

from crypto_trailing_stop.commons.constants import (
    ADX_THRESHOLD_VALUES,
    EMA_SHORT_MID_PAIRS,
    MAX_VOLUME_THRESHOLD_VALUES,
    MIN_VOLUME_THRESHOLD_VALUES,
    SP_TP_PAIRS,
    YES_NO_VALUES,
)
from crypto_trailing_stop.config.configuration_properties import ConfigurationProperties
from crypto_trailing_stop.infrastructure.services.vo.buy_sell_signals_config_item import BuySellSignalsConfigItem
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder


class BuySellSignalsConfigForm(Form):
    ema_short_and_mid: str = FormField(
        enter_message_text="📈📉 Select EMA Short and Mid",
        error_message_text=f"❌ Invalid EMA Short/Mid value. Valid values: {', '.join(EMA_SHORT_MID_PAIRS)}",
        filter=F.text.in_(EMA_SHORT_MID_PAIRS) & F.text,
        reply_markup=ReplyKeyboardBuilder()
        .add(*(KeyboardButton(text=text) for text in EMA_SHORT_MID_PAIRS))
        .as_markup(),
    )
    # NOTE: [JMSOLA] Currently not used in the strategy, but kept for future use
    # ema_long: int = FormField(
    #     enter_message_text="📐 Select EMA Long",
    #     error_message_text="❌ Invalid EMA Long value. Valid values: "
    #     + f"{', '.join([str(value) for value in EMA_LONG_VALUES])}",
    #     filter=F.text.in_([str(value) for value in EMA_LONG_VALUES]) & F.text,
    #     reply_markup=ReplyKeyboardBuilder()
    #     .add(*(KeyboardButton(text=str(value)) for value in EMA_LONG_VALUES))
    #     .as_markup(),
    # )
    sp_tp_atr_factor_pair: str = FormField(
        enter_message_text="🛡️🏁 Select SL ATR x / TP ATR x",
        error_message_text=f"❌ Invalid SL/TP ATR values. Valid values: {', '.join(SP_TP_PAIRS)}",
        filter=F.text.in_(SP_TP_PAIRS) & F.text,
        reply_markup=KeyboardsBuilder.get_sp_tp_pairs_keyboard(),
    )
    enable_adx_filter: str = FormField(
        enter_message_text="📶 Enable ADX Filter?",
        error_message_text=f"❌ Invalid value. Valid values: {', '.join(YES_NO_VALUES)}",
        filter=F.text.in_(YES_NO_VALUES) & F.text,
        reply_markup=ReplyKeyboardBuilder().add(*(KeyboardButton(text=text) for text in YES_NO_VALUES)).as_markup(),
    )
    adx_threshold: int = FormField(
        enter_message_text="🔦 Select ADX Threshold",
        error_message_text="❌ Invalid ADX Threshold value. Valid values: "
        + f"{', '.join([str(value) for value in ADX_THRESHOLD_VALUES])}",
        filter=F.text.in_([str(value) for value in ADX_THRESHOLD_VALUES]) & F.text,
        reply_markup=ReplyKeyboardBuilder()
        .add(*(KeyboardButton(text=str(value)) for value in ADX_THRESHOLD_VALUES))
        .as_markup(),
    )
    enable_buy_volume_filter: str = FormField(
        enter_message_text="🚩 Enable BUY Volume Filter?",
        error_message_text=f"❌ Invalid value. Valid values: {', '.join(YES_NO_VALUES)}",
        filter=F.text.in_(YES_NO_VALUES) & F.text,
        reply_markup=ReplyKeyboardBuilder().add(*(KeyboardButton(text=text) for text in YES_NO_VALUES)).as_markup(),
    )
    buy_min_volume_threshold: float = FormField(
        enter_message_text="🔊 Select BUY Min. Volume Threshold",
        error_message_text="❌ Invalid BUY Min. Volume Threshold value. Valid values: "
        + f"{', '.join([str(value) for value in MIN_VOLUME_THRESHOLD_VALUES])}",
        filter=F.text.in_([str(value) for value in MIN_VOLUME_THRESHOLD_VALUES]) & F.text,
        reply_markup=KeyboardsBuilder.get_volume_threshold_keyboard(MIN_VOLUME_THRESHOLD_VALUES),
    )
    buy_max_volume_threshold: float = FormField(
        enter_message_text="🔇 Select BUY Max. Volume Threshold",
        error_message_text="❌ Invalid BUY Max. Volume Threshold value. Valid values: "
        + f"{', '.join([str(value) for value in MAX_VOLUME_THRESHOLD_VALUES])}",
        filter=F.text.in_([str(value) for value in MAX_VOLUME_THRESHOLD_VALUES]) & F.text,
        reply_markup=KeyboardsBuilder.get_volume_threshold_keyboard(MAX_VOLUME_THRESHOLD_VALUES),
    )
    enable_sell_volume_filter: str = FormField(
        enter_message_text="💣 Enable SELL Volume Filter?",
        error_message_text=f"❌ Invalid value. Valid values: {', '.join(YES_NO_VALUES)}",
        filter=F.text.in_(YES_NO_VALUES) & F.text,
        reply_markup=ReplyKeyboardBuilder().add(*(KeyboardButton(text=text) for text in YES_NO_VALUES)).as_markup(),
    )
    sell_min_volume_threshold: float = FormField(
        enter_message_text="🔊 Select SELL Min. Volume Threshold",
        error_message_text="❌ Invalid SELL Min. Volume Threshold value. Valid values: "
        + f"{', '.join([str(value) for value in MIN_VOLUME_THRESHOLD_VALUES])}",
        filter=F.text.in_([str(value) for value in MIN_VOLUME_THRESHOLD_VALUES]) & F.text,
        reply_markup=KeyboardsBuilder.get_volume_threshold_keyboard(MIN_VOLUME_THRESHOLD_VALUES),
    )
    # NOTE: [JMSOLA] Always is enabled in the strategy, so no need to configure it for now
    # enable_exit_on_sell_signal: str = FormField(
    #     enter_message_text="🚨 Enable Exit on SELL Signal?",
    #     error_message_text=f"❌ Invalid value. Valid values: {', '.join(YES_NO_VALUES)}",
    #     filter=F.text.in_(YES_NO_VALUES) & F.text,
    #     reply_markup=ReplyKeyboardBuilder().add(*(KeyboardButton(text=text) for text in YES_NO_VALUES)).as_markup(),
    # )
    enable_exit_on_take_profit: str = FormField(
        enter_message_text="🎯 Enable Exit on Take Profit?",
        error_message_text=f"❌ Invalid value. Valid values: {', '.join(YES_NO_VALUES)}",
        filter=F.text.in_(YES_NO_VALUES) & F.text,
        reply_markup=ReplyKeyboardBuilder().add(*(KeyboardButton(text=text) for text in YES_NO_VALUES)).as_markup(),
    )

    def to_persistable(
        self, symbol: str, *, configuration_properties: ConfigurationProperties
    ) -> BuySellSignalsConfigItem:
        ema_short_value, ema_mid_value = tuple(map(int, self.ema_short_and_mid.split("/")))
        stop_loss_atr_multiplier, take_profit_atr_multiplier = tuple(map(float, self.sp_tp_atr_factor_pair.split("/")))
        ret = BuySellSignalsConfigItem(
            symbol=symbol,
            ema_short_value=ema_short_value,
            ema_mid_value=ema_mid_value,
            # NOTE: [JMSOLA] Currently not used in the strategy, but kept for future use
            # ema_long_value=int(self.ema_long),
            ema_long_value=configuration_properties.buy_sell_signals_ema_long_value,
            stop_loss_atr_multiplier=stop_loss_atr_multiplier,
            take_profit_atr_multiplier=take_profit_atr_multiplier,
            enable_adx_filter=bool(self.enable_adx_filter.lower() == "yes"),
            adx_threshold=int(self.adx_threshold),
            enable_buy_volume_filter=bool(self.enable_buy_volume_filter.lower() == "yes"),
            buy_min_volume_threshold=float(self.buy_min_volume_threshold),
            buy_max_volume_threshold=float(self.buy_max_volume_threshold),
            enable_sell_volume_filter=bool(self.enable_sell_volume_filter.lower() == "yes"),
            sell_min_volume_threshold=float(self.sell_min_volume_threshold),
            # NOTE: [JMSOLA] Always is enabled in the strategy, so no need to configure it for now
            # enable_exit_on_sell_signal=bool(self.enable_exit_on_sell_signal.lower() == "yes"),
            enable_exit_on_sell_signal=True,
            enable_exit_on_take_profit=bool(self.enable_exit_on_take_profit.lower() == "yes"),
        )
        return ret
