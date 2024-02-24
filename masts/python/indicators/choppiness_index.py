import numpy as np

class choppiness_index:
    @staticmethod
    def calculate(close_prices, period=14):
        high_price = np.max(close_prices[-period:])
        low_price = np.min(close_prices[-period:])
        price_range = high_price - low_price

        volatility = np.mean(np.abs(np.diff(close_prices[-period:])))

        choppiness = 100 * np.log10((price_range / volatility) / np.log10(period))
        return choppiness