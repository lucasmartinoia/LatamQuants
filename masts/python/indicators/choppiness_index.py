from numpy import log10 as npLog10
import talib

class choppiness_index:
    @staticmethod
    def calculate(high, low, close, length=14, atr_length=None, ln=None, scalar=None):
        """Indicator: Choppiness Index (CHOP)"""
        # Validate Arguments
        length = int(length) if length and length > 0 else 14
        atr_length = int(atr_length) if atr_length is not None and atr_length > 0 else 1
        ln = bool(ln) if isinstance(ln, bool) else False
        scalar = float(scalar) if scalar else 100

        if high is None or low is None or close is None: return

        # Calculate Result
        diff = high.rolling(length).max() - low.rolling(length).min()

        atr_ = talib.ATR(high=high, low=low, close=close, timeperiod=atr_length)
        atr_sum = atr_.rolling(length).sum()

        chop = scalar
        chop *= npLog10(atr_sum / diff) / npLog10(length)

        return chop