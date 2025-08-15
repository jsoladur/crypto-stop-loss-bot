from aiogram import F
from aiogram.types import KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram3_form import Form, FormField

from crypto_trailing_stop.commons.constants import (
    ADX_THRESHOLD_VALUES,
    EMA_LONG_VALUES,
    EMA_SHORT_MID_PAIRS,
    SP_TP_PAIRS,
    VOLUME_THRESHOLD_VALUES,
    YES_NO_VALUES,
)
from crypto_trailing_stop.infrastructure.services.vo.buy_sell_signals_config_item import BuySellSignalsConfigItem
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder


class BuySellSignalsConfigForm(Form):
    ema_short_and_mid: str = FormField(
        enter_message_text="📈📉 Select EMA short and mid",
        error_message_text=f"❌ Invalid EMA short and mid value. Valid values: {', '.join(EMA_SHORT_MID_PAIRS)}",
        filter=F.text.in_(EMA_SHORT_MID_PAIRS) & F.text,
        reply_markup=ReplyKeyboardBuilder()
        .add(*(KeyboardButton(text=text) for text in EMA_SHORT_MID_PAIRS))
        .as_markup(),
    )
    ema_long: int = FormField(
        enter_message_text="📐 Select EMA Long",
        error_message_text="❌ Invalid EMA Long value. Valid values: "
        + f"{', '.join([str(value) for value in EMA_LONG_VALUES])}",
        filter=F.text.in_([str(value) for value in EMA_LONG_VALUES]) & F.text,
        reply_markup=ReplyKeyboardBuilder()
        .add(*(KeyboardButton(text=str(value)) for value in EMA_LONG_VALUES))
        .as_markup(),
    )
    sp_tp_atr_factor_pair: str = FormField(
        enter_message_text="🛡️🏁  Select Stop Loss and Take Profit Factors",
        error_message_text=f"❌ Invalid Stop Loss and Take Profit Factors values. Valid values: {', '.join(SP_TP_PAIRS)}",  # noqa: E501
        filter=F.text.in_(SP_TP_PAIRS) & F.text,
        reply_markup=KeyboardsBuilder.get_sp_tp_pairs_keyboard(),
    )
    filter_noise_using_adx: str = FormField(
        enter_message_text="📶 Filter Noise using ADX?",
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
    apply_volume_filter: str = FormField(
        enter_message_text="🚩 Apply Relative Volume Filter?",
        error_message_text=f"❌ Invalid value. Valid values: {', '.join(YES_NO_VALUES)}",
        filter=F.text.in_(YES_NO_VALUES) & F.text,
        reply_markup=ReplyKeyboardBuilder().add(*(KeyboardButton(text=text) for text in YES_NO_VALUES)).as_markup(),
    )
    volume_threshold: float = FormField(
        enter_message_text="🔊 Select Volume Threshold",
        error_message_text="❌ Invalid Volume Threshold value. Valid values: "
        + f"{', '.join([str(value) for value in VOLUME_THRESHOLD_VALUES])}",
        filter=F.text.in_([str(value) for value in VOLUME_THRESHOLD_VALUES]) & F.text,
        reply_markup=ReplyKeyboardBuilder()
        .add(*(KeyboardButton(text=str(value)) for value in VOLUME_THRESHOLD_VALUES))
        .as_markup(),
    )
    auto_exit_sell_1h: str = FormField(
        enter_message_text="🚨 Auto-Exit SELL 1H enabled?",
        error_message_text=f"❌ Invalid value. Valid values: {', '.join(YES_NO_VALUES)}",
        filter=F.text.in_(YES_NO_VALUES) & F.text,
        reply_markup=ReplyKeyboardBuilder().add(*(KeyboardButton(text=text) for text in YES_NO_VALUES)).as_markup(),
    )
    auto_exit_atr_take_profit: str = FormField(
        enter_message_text="🎯 Auto-Exit Take Profit enabled?",
        error_message_text=f"❌ Invalid value. Valid values: {', '.join(YES_NO_VALUES)}",
        filter=F.text.in_(YES_NO_VALUES) & F.text,
        reply_markup=ReplyKeyboardBuilder().add(*(KeyboardButton(text=text) for text in YES_NO_VALUES)).as_markup(),
    )

    def to_persistable(self, symbol: str) -> BuySellSignalsConfigItem:
        ema_short_value, ema_mid_value = tuple(map(int, self.ema_short_and_mid.split("/")))
        stop_loss_atr_multiplier, take_profit_atr_multiplier = tuple(map(float, self.sp_tp_atr_factor_pair.split("/")))
        ret = BuySellSignalsConfigItem(
            symbol=symbol,
            ema_short_value=ema_short_value,
            ema_mid_value=ema_mid_value,
            ema_long_value=int(self.ema_long),
            stop_loss_atr_multiplier=stop_loss_atr_multiplier,
            take_profit_atr_multiplier=take_profit_atr_multiplier,
            filter_noise_using_adx=bool(self.filter_noise_using_adx.lower() == "yes"),
            adx_threshold=int(self.adx_threshold),
            apply_volume_filter=bool(self.apply_volume_filter.lower() == "yes"),
            volume_threshold=float(self.volume_threshold),
            auto_exit_sell_1h=bool(self.auto_exit_sell_1h.lower() == "yes"),
            auto_exit_atr_take_profit=bool(self.auto_exit_atr_take_profit.lower() == "yes"),
        )
        return ret
