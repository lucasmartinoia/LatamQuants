from python.common.logging_config import logger
from calculus import get_exchange_rate

class RiskManagement:
    def __init__(self, dma, initial_balance, balance_currency, max_risk_rate, max_drawdown_rate):
        self.dma = dma
        self.initial_balance = initial_balance
        self.balance_currency = balance_currency
        self.max_risk_rate = max_risk_rate
        self.max_drawdown_rate = max_drawdown_rate


    def get_free_risk(self, date_time):
        current_balance = self.dma.account_info["balance"] # TODO: verifies if it works
        risk_consumed_rate, risk_consumed_amount = self.get_current_risk_consumed(current_balance, date_time)
        free_risk_rate = self.max_risk_rate - risk_consumed_rate
        free_risk_amount = current_balance - risk_consumed_rate
        return free_risk_rate, free_risk_amount

    # Return risk current consumed percentage (rate) and amount in balance currency.
    def get_current_risk_consumed(self, current_balance, date_time):
        risk_consumed_amount = 0.0
        for trade_data in self.dma.open_orders:
            risk_consumed_amount = risk_consumed_amount + self.get_order_risk_amount(trade_data, date_time)
        risk_consumed_rate = risk_consumed_amount / current_balance
        return risk_consumed_rate, risk_consumed_amount

    # Returns the risk amount in balance currency for a given open or pending order.
    def get_order_risk_amount(self, trade_data, date_time):
        # TODO: Get contract_size from symbol information
        contract_size = 100000
        logger.error(f"Ora for ticket_no: {trade_data['ticket_no']}, {trade_data['symbol']}, {trade_data['type']}")
        # Get exchange rate
        base_currency = trade_data['symbol'][:3]
        quote_currency = self.balance_currency
        exchange_rate = get_exchange_rate(base_currency, quote_currency, date_time)
        logger.error(f"order base ccy: {base_currency}, balance ccy: {quote_currency}, exchange_rate: {exchange_rate}")
        # Calculate Ora
        order_risk_amount = (trade_data["open_price"]-trade_data["stop_loss"])*trade_data["lots"]*contract_size
        logger.error(f"Ora in base ccy: {order_risk_amount}")
        order_risk_amount = order_risk_amount * exchange_rate
        logger.error(f"Ora in blance ccy: {order_risk_amount}")
        if trade_data['type'].startswith('sell'):
            order_risk_amount = order_risk_amount * (-1)
        # TODO: in case of negative Ora (we'll consider it as leverage), it'll necessary to substract order cost to be more realistic.
        logger.error(f"Ora to return: {order_risk_amount}")
        return order_risk_amount

    # Returns order lots for a new order taking into account risk available amount for the order in the strategy.
    # Risk available amount have to be expressed in base currency.
    def get_new_order_size(self, trade_data, date_time, risk_available_amount):
        # TODO: calculate order size
        return 0

    def get_strategy_risk_available(self):