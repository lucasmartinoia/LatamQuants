from istrategy import IStrategy

class DivergentT1(IStrategy):

    def __init__(self, smart_trader, symbol, timeframe, max_risk_per_trade):
        super().__init__(smart_trader, symbol, timeframe, max_risk_per_trade)  # Call the constructor of the base class
        self.required_data = self.set_required_bars()

    def set_required_bars(self):

