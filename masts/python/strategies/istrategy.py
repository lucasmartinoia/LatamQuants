from abc import ABC, abstractmethod

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

    @property
    @abstractmethod
    def required_data(self):
        return self.required_data
