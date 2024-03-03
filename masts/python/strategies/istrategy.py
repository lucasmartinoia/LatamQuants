from abc import ABC, abstractmethod
from enum import Enum
from python.common.risk_management import RiskManagement

class SignalType(Enum):
    NONE = 0
    BUY = 1
    SELL = 2

class MarketTrend(Enum):
    UNDEFINED = 0
    BULL = 1
    BEAR = 2
    SIDEWAYS = 3

class MarketEnergy(Enum):
    NOT_SIGNIFICANT = 0
    VERY_HIGH = 1
    HIGH = 2
    LOW = 3
    VERY_LOW = 4

# Define the interface (abstract base class)
class IStrategy(ABC):

    def __init__(self, smart_trader, magic_no, symbol, timeframe, max_risk_perc_trade, max_consecutive_losses, symbol_spec):
        self.smart_trader = smart_trader
        self.magic_no = magic_no
        self.symbol = symbol
        self.timeframe = timeframe
        self.max_risk_perc_trade = max_risk_perc_trade
        self.max_consecutive_losses = max_consecutive_losses
        self.symbol_spec = symbol_spec
        self.required_data = {}
        self.name = "DivergentT1"
        self.id = f"{self.name}_{symbol}_{timeframe}"
        self.smart_trader.risk_management.set_strategy_risk(self.id, self.symbol, self.symbol_spec, self.max_risk_perc_trade, self.max_consecutive_losses)

    @abstractmethod
    def execute(self, historic_data):
        pass

    @abstractmethod
    def manage_orders(self):
        pass

    @abstractmethod
    def required_data(self):
        pass
