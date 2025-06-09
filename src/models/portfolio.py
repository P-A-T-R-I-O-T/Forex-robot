def update_balance(self, currency: str, amount: float):
    """
    Обновляет баланс портфеля.

    Args:
        currency: Валюта
        amount: Сумма
    """
    if currency not in self.balances:
        self.balances[currency] = {'total': 0, 'available': 0}

    self.balances[currency]['total'] += amount
    self.balances[currency]['available'] += amount


def update_position(self, figi: str, amount: float, price: float):
    """
    Обновляет позицию по инструменту.

    Args:
        figi: Идентификатор инструмента
        amount: Количество
        price: Цена
    """
    if figi not in self.positions:
        self.positions[figi] = {
            'figi': figi,
            'quantity': 0,
            'average_price': 0
        }

    current = self.positions[figi]
    new_quantity = current['quantity'] + amount
    if new_quantity == 0:
        self.positions.pop(figi)
    else:
        current['average_price'] = (
                                           current['average_price'] * current['quantity'] + price * amount
                                   ) / new_quantity
        current['quantity'] = new_quantity


def total_equity(self) -> float:
    """
    Рассчитывает общую стоимость портфеля.

    Returns:
        Суммарная стоимость
    """
    total = 0
    for currency, balance in self.balances.items():
        total += balance['total']
    return total