from abc import ABC, abstractmethod
from enum import Enum


class SignalType(Enum):
    NONE = 0
    BUY = 1
    SELL = 2

class MarketTrend(Enum):
    UNDEFINED = 0
    BULL = 1
    BEAR = 2
    SIDEWAYS = 3


# Define the interface (abstract base class)
class IStrategy(ABC):

    def __init__(self, smart_trader, symbol, timeframe, max_risk_per_trade):
        self.smart_trader = smart_trader
        self.symbol = symbol
        self.timeframe = timeframe
        self.max_risk_per_trade = max_risk_per_trade
        self.required_data = {}

    @abstractmethod
    def execute(self, amount):
        pass

    @abstractmethod
    def manage_orders(self):
        pass

    @abstractmethod
    def required_data(self):
        pass
