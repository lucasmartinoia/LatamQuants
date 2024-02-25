from python.common.logging_config import logger
from python.common.calculus import get_exchange_rate, normalize_order_size

class RiskManagement:
    def __init__(self, dma, initial_balance, balance_currency, max_risk_perc, max_drawdown_perc):
        self.dma = dma
        self.initial_balance = initial_balance
        self.balance_currency = balance_currency
        self.max_risk_perc = max_risk_perc
        self.max_drawdown_perc = max_drawdown_perc
        self.strategies = {}
        self.symbol_specs = {}

    def set_strategy_risk(self, strategy_id, symbol, symbol_spec, max_risk_perc_trade, max_consecutive_losses):
        self.strategies[strategy_id] = {'max_risk_perc_trade': max_risk_perc_trade, 'max_consecutive_losses': max_consecutive_losses}
        self.symbol_specs[symbol] = symbol_spec

    def max_drawdown_reached(self):
        current_balance = self.dma.account_info["balance"]
        result = (1-(current_balance/self.initial_balance))*100 >= self.max_drawdown_perc
        if result:
            logger.info(f'MAX DRAWDOWN REACHED! initial_balance: {self.initial_balance}, current_balance: {current_balance}, max_drawdown_perc: {self.max_drawdown_perc}')
            self.dma.ACTIVE = False
        return result

    def get_free_risk(self, date_time):
        current_balance = self.dma.account_info["balance"]
        risk_consumed_perc, risk_consumed_amount = self.get_current_risk_consumed(current_balance, date_time)
        free_risk_perc = 100.0 - risk_consumed_perc
        free_risk_amount = current_balance - risk_consumed_perc
        return free_risk_perc, free_risk_amount

    # Return risk current consumed percentage (rate) and amount in balance currency.
    def get_current_risk_consumed(self, current_balance, date_time):
        risk_consumed_amount = 0.0
        for trade_data in self.dma.open_orders:
            risk_consumed_amount = risk_consumed_amount + self.calculate_order_risk_amount(trade_data, date_time)
        risk_consumed_perc = risk_consumed_amount / current_balance * 100.0
        return risk_consumed_perc, risk_consumed_amount

    # Returns the risk amount in balance currency for a given open or pending order.
    def calculate_order_risk_amount(self, trade_data, date_time):
        contract_size = self.symbol_specs[trade_data['symbol']]['contract_size']
        # Get exchange rate
        base_currency = trade_data['symbol'][:3]
        quote_currency = self.balance_currency
        exchange_rate = get_exchange_rate(base_currency, quote_currency, date_time)
        logger.error(f"order base ccy: {base_currency}, balance ccy: {quote_currency}, exchange_rate: {exchange_rate}")
        # Calculate Risk Amount
        order_risk_amount = abs(trade_data["open_price"]-trade_data["stop_loss"]) * trade_data["lots"] * contract_size
        logger.error(f"Ora in base ccy: {order_risk_amount}")
        order_risk_amount = order_risk_amount * exchange_rate
        logger.error(f"Ora in blance ccy: {order_risk_amount}")
        # TODO: in case of negative Ora (we'll consider it as leverage), it'll necessary to substract order cost to be more realistic.
        logger.error(f"Ora to return: {order_risk_amount}")
        return order_risk_amount

    # Returns the order size.
    def calculate_order_size(self, symbol, open_price, stop_loss, order_amount_balance_ccy, date_time):
        contract_size = self.symbol_specs[symbol]['contract_size']
        min_volume = self.symbol_specs[symbol]['min_volume']
        # Get exchange rate
        base_currency = symbol[:3]
        quote_currency = self.balance_currency
        exchange_rate = get_exchange_rate(quote_currency, base_currency, date_time)
        logger.error(f"order base ccy: {base_currency}, balance ccy: {quote_currency}, exchange_rate: {exchange_rate}")
        # Calculate Order Size
        order_amount = order_amount_balance_ccy * exchange_rate
        order_size = order_amount / (abs(open_price - stop_loss) * contract_size)
        order_size = normalize_order_size(order_size, min_volume)
        return order_size

    # Returns order lots for a new order taking into account risk available amount for the order in the strategy.
    # Risk available amount have to be expressed in base currency, min size allowed.
    def get_new_order_size(self, strategy_id, symbol, open_price, stop_loss, date_time):
        result = 0.0
        if not self.max_drawdown_reached():
            free_risk_perc, free_risk_amount = self.get_free_risk(date_time)
            if free_risk_amount > 0:
                order_amount_balance_ccy = free_risk_amount * (self.strategies[strategy_id]['max_risk_perc_trade'] / 100.0)
                result = self.calculate_order_size(symbol, open_price, stop_loss, order_amount_balance_ccy, date_time)
        return result

    # TODO: this function
    #def get_strategy_risk_available(self):