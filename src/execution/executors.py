# Исполнитель торговых операций
class TradeExecutor:
    def __init__(self, client):
        self.client = client  # Клиент API Тинькофф

    def execute_order(self, order):
        """Отправка ордера на биржу"""
        if order['type'] == 'market':
            self.client.orders.post_order(
                figi=order['figi'],  # Идентификатор инструмента
                quantity=order['lots'],  # Количество лотов
                direction=OrderDirection.ORDER_DIRECTION_BUY,  # Направление сделки
                account_id=ACCOUNT_ID,  # Идентификатор счета
                order_type=OrderType.ORDER_TYPE_MARKET  # Тип ордера
            )