"""
Интерфейс командной строки для Forex Trading Bot.

Этот модуль предоставляет:
- Интерактивную систему меню
- Мониторинг в реальном времени
- Управление ручной торговлей
- Отчетность и визуализацию
"""

import asyncio
from typing import Optional
from datetime import datetime, timedelta

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich.progress import Progress
import questionary

from src.core.app import ForexTradingBot
from src.api.tinkoff_api import TinkoffAPI
from src.utils.config import Config


class CLIInterface:
    """
    Интерфейс командной строки для взаимодействия с Forex Trading Bot.

    Атрибуты:
        bot (ForexTradingBot): Основной экземпляр приложения
        console (Console): Rich console для вывода
        layout (Layout): Менеджер макета UI
        live (Live): Live display для обновлений в реальном времени
    """

    def __init__(self, bot: ForexTradingBot):
        """
        Инициализация CLI интерфейса.

        Аргументы:
            bot: Экземпляр ForexTradingBot
        """
        self.bot = bot
        self.console = Console()
        self.layout = Layout()
        self.live: Optional[Live] = None
        self._running = False

    async def run(self):
        """Запуск основного CLI интерфейса."""
        self._running = True

        # Начальная настройка
        await self._setup_interface()

        # Основной цикл меню
        while self._running:
            try:
                choice = await self._main_menu()

                if choice == "Real-time Monitoring":
                    await self._real_time_monitoring()
                elif choice == "Manual Trading":
                    await self._manual_trading()
                elif choice == "Reports":
                    await self._reports_menu()
                elif choice == "Configuration":
                    await self._configuration_menu()
                elif choice == "Exit":
                    self._running = False

            except KeyboardInterrupt:
                self._running = False
            except Exception as e:
                self.console.print(f"[red]Ошибка: {e}[/red]")
                await asyncio.sleep(1)

    async def _setup_interface(self):
        """Настройка начального макета интерфейса."""
        self.layout.split(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=3),
        )

        # Приветственное сообщение
        welcome = Panel(
            "Forex Trading Bot - Tinkoff API v2",
            subtitle="Automated Trading System",
            style="bold blue",
        )
        self.layout["header"].update(welcome)

        # Начальное содержимое main
        self.layout["main"].update(
            Panel("Выберите пункт меню для начала", style="dim")
        )

        # Footer со статусом
        self._update_footer()

    async def _main_menu(self) -> str:
        """Отображение главного меню и получение выбора пользователя."""
        choices = [
            "Real-time Monitoring",
            "Manual Trading",
            "Reports",
            "Configuration",
            "Exit",
        ]

        question = questionary.select(
            "Выберите опцию:",
            choices=choices,
        )

        return await question.ask_async()

    async def _real_time_monitoring(self):
        """Отображение мониторинга в реальном времени."""
        self.console.print("[bold]Загрузка данных в реальном времени...[/bold]")

        # Создание live display
        with Live(auto_refresh=False) as live:
            self.live = live

            while self._running:
                try:
                    # Получение текущего статуса портфеля
                    portfolio = await self.bot.portfolio.get_current_portfolio()

                    # Получение метрик производительности
                    metrics = await self.bot.trading_engine.get_performance_report()

                    # Создание таблицы для портфеля
                    portfolio_table = Table(title="Статус портфеля")
                    portfolio_table.add_column("Валюта")
                    portfolio_table.add_column("Баланс", justify="right")
                    portfolio_table.add_column("Доступно", justify="right")

                    for currency, balance in portfolio.balances.items():
                        portfolio_table.add_row(
                            currency,
                            f"{balance.total:.2f}",
                            f"{balance.available:.2f}",
                        )

                    # Создание таблицы для производительности
                    metrics_table = Table(title="Метрики производительности")
                    metrics_table.add_column("Метрика")
                    metrics_table.add_column("Значение", justify="right")

                    for name, value in metrics.items():
                        if isinstance(value, float):
                            value_str = f"{value:.2f}"
                        else:
                            value_str = str(value)

                        color = "green" if (name == "total_profit_loss" and value > 0) else (
                            "red" if (name == "total_profit_loss" and value < 0) else ""
                        )

                        metrics_table.add_row(
                            name.replace("_", " ").title(),
                            f"[{color}]{value_str}[/{color}]",
                        )

                    # Создание таблицы для открытых сделок
                    trades_table = Table(title="Активные сделки")
                    trades_table.add_column("Инструмент")
                    trades_table.add_column("Направление")
                    trades_table.add_column("Цена входа", justify="right")
                    trades_table.add_column("Текущая цена", justify="right")
                    trades_table.add_column("P/L", justify="right")
                    trades_table.add_column("Стратегия")

                    for trade in self.bot.trading_engine.active_trades.values():
                        # Получение текущей цены
                        prices = await self.bot.api.get_current_prices([trade.figi])
                        current_price = prices.get(trade.figi, trade.executed_price)

                        # Расчет P/L
                        if trade.direction == "buy":
                            pl = (current_price - trade.executed_price) * trade.executed_quantity
                        else:
                            pl = (trade.executed_price - current_price) * trade.executed_quantity

                        pl_color = "green" if pl > 0 else "red"

                        trades_table.add_row(
                            trade.figi,
                            trade.direction,
                            f"{trade.executed_price:.4f}",
                            f"{current_price:.4f}",
                            f"[{pl_color}]{pl:.2f}[/{pl_color}]",
                            trade.strategy,
                        )

                    # Обновление макета
                    self.layout["main"].update(
                        Panel(
                            Layout(
                                Layout(portfolio_table, name="top"),
                                Layout(
                                    Layout(metrics_table, name="left"),
                                    Layout(trades_table, name="right"),
                                    name="middle",
                                ),
                            ),
                            title="Мониторинг в реальном времени",
                        )
                    )

                    self.live.update(self.layout)
                    await asyncio.sleep(5)

                except KeyboardInterrupt:
                    self.live = None
                    return
                except Exception as e:
                    self.console.print(f"[red]Ошибка мониторинга: {e}[/red]")
                    await asyncio.sleep(1)

    async def _manual_trading(self):
        """Интерфейс ручной торговли."""
        while self._running:
            try:
                choices = [
                    "Place Trade",
                    "Close Trade",
                    "Back to Main Menu",
                ]

                choice = await questionary.select(
                    "Опции ручной торговли:",
                    choices=choices,
                ).ask_async()

                if choice == "Place Trade":
                    await self._place_manual_trade()
                elif choice == "Close Trade":
                    await self._close_manual_trade()
                elif choice == "Back to Main Menu":
                    return

            except KeyboardInterrupt:
                return
            except Exception as e:
                self.console.print(f"[red]Ошибка: {e}[/red]")
                await asyncio.sleep(1)

    async def _place_manual_trade(self):
        """Размещение ручной сделки."""
        # Получение доступных инструментов
        instruments = list(self.bot.api.instruments.values())
        instrument_names = [f"{i.name} ({i.figi})" for i in instruments]

        # Выбор инструмента
        instrument_choice = await questionary.select(
            "Выберите инструмент:",
            choices=instrument_names,
        ).ask_async()

        figi = instruments[instrument_names.index(instrument_choice)].figi

        # Выбор направления
        direction = await questionary.select(
            "Выберите направление:",
            choices=["Buy", "Sell"],
        ).ask_async()

        # Получение суммы
        amount = await questionary.text(
            "Введите сумму (в валюте):",
            validate=lambda x: x.replace(".", "", 1).isdigit(),
        ).ask_async()

        amount = float(amount)

        # Выбор типа ордера
        order_type = await questionary.select(
            "Выберите тип ордера:",
            choices=["Market", "Limit"],
        ).ask_async()

        price = None
        if order_type == "Limit":
            price = await questionary.text(
                "Введите лимитную цену:",
                validate=lambda x: x.replace(".", "", 1).isdigit(),
            ).ask_async()
            price = float(price)

        # Подтверждение сделки
        confirm = await questionary.confirm(
            f"Подтвердить {direction} {amount} {instrument_choice} по цене {price if price else 'рыночной'}?"
        ).ask_async()

        if confirm:
            with self.console.status("[bold green]Исполнение сделки..."):
                success, trade = await self.bot.trading_engine.manual_trade(
                    figi=figi,
                    direction=direction.lower(),
                    amount=amount,
                    order_type=order_type.lower(),
                    price=price,
                )

                if success:
                    self.console.print(
                        f"[green]Сделка успешно исполнена![/green]\n"
                        f"Инструмент: {trade.figi}\n"
                        f"Направление: {trade.direction}\n"
                        f"Количество: {trade.executed_quantity}\n"
                        f"Цена: {trade.executed_price:.4f}"
                    )
                else:
                    self.console.print("[red]Не удалось исполнить сделку![/red]")

                await asyncio.sleep(2)

    async def _close_manual_trade(self):
        """Закрытие ручной сделки."""
        if not self.bot.trading_engine.active_trades:
            self.console.print("[yellow]Нет активных сделок для закрытия[/yellow]")
            await asyncio.sleep(1)
            return

        # Выбор сделки для закрытия
        trade_choices = [
            f"{trade.figi} ({trade.direction} {trade.executed_quantity} @ {trade.executed_price:.4f})"
            for trade in self.bot.trading_engine.active_trades.values()
        ]

        trade_choice = await questionary.select(
            "Выберите сделку для закрытия:",
            choices=trade_choices,
        ).ask_async()

        trade = list(self.bot.trading_engine.active_trades.values())[
            trade_choices.index(trade_choice)
        ]

        # Подтверждение закрытия
        confirm = await questionary.confirm(
            f"Подтвердить закрытие сделки {trade.figi}?"
        ).ask_async()

        if confirm:
            with self.console.status("[bold green]Закрытие сделки..."):
                exit_direction = (
                    "sell" if trade.direction == "buy" else "buy"
                )

                success, exit_trade = await self.bot.trading_engine.manual_trade(
                    figi=trade.figi,
                    direction=exit_direction,
                    amount=trade.executed_quantity * trade.executed_price,
                    order_type="market",
                )

                if success:
                    # Расчет прибыли/убытка
                    profit = (
                        (exit_trade.executed_price - trade.executed_price) * trade.executed_quantity
                        if trade.direction == "buy"
                        else (trade.executed_price - exit_trade.executed_price) * trade.executed_quantity
                    )

                    color = "green" if profit > 0 else "red"

                    self.console.print(
                        f"[{color}]Сделка закрыта с P/L: {profit:.2f}[/{color}]\n"
                        f"Вход: {trade.executed_price:.4f}\n"
                        f"Выход: {exit_trade.executed_price:.4f}"
                    )
                else:
                    self.console.print("[red]Не удалось закрыть сделку![/red]")

                await asyncio.sleep(2)

    async def _reports_menu(self):
        """Меню отчетов и аналитики."""
        while self._running:
            try:
                choices = [
                    "Trade History",
                    "Performance Analytics",
                    "Market Data",
                    "Back to Main Menu",
                ]

                choice = await questionary.select(
                    "Отчеты и аналитика:",
                    choices=choices,
                ).ask_async()

                if choice == "Trade History":
                    await self._show_trade_history()
                elif choice == "Performance Analytics":
                    await self._show_performance_analytics()
                elif choice == "Market Data":
                    await self._show_market_data()
                elif choice == "Back to Main Menu":
                    return

            except KeyboardInterrupt:
                return
            except Exception as e:
                self.console.print(f"[red]Ошибка: {e}[/red]")
                await asyncio.sleep(1)

    async def _show_trade_history(self):
        """Отображение истории сделок."""
        trades = await self.bot.data_manager.get_trade_history(days=30)

        if not trades:
            self.console.print("[yellow]Нет доступной истории сделок[/yellow]")
            await asyncio.sleep(1)
            return

        table = Table(title="История сделок (последние 30 дней)")
        table.add_column("Дата")
        table.add_column("Инструмент")
        table.add_column("Направление")
        table.add_column("Количество")
        table.add_column("Цена входа", justify="right")
        table.add_column("Цена выхода", justify="right")
        table.add_column("P/L", justify="right")
        table.add_column("Стратегия")

        for trade in trades:
            if not hasattr(trade, "exit_price"):
                continue

            profit = trade.get("profit", 0)
            color = "green" if profit > 0 else "red"

            table.add_row(
                trade.get("timestamp", "").strftime("%Y-%m-%d %H:%M"),
                trade.get("figi", ""),
                trade.get("direction", ""),
                str(trade.get("executed_quantity", "")),
                f"{trade.get('executed_price', 0):.4f}",
                f"{trade.get('exit_price', 0):.4f}",
                f"[{color}]{profit:.2f}[/{color}]",
                trade.get("strategy", ""),
            )

        self.console.print(table)
        await questionary.press_any_key_to_continue().ask_async()

    async def _show_performance_analytics(self):
        """Отображение аналитики производительности."""
        # Получение метрик производительности
        metrics = await self.bot.trading_engine.get_performance_report()

        # Получение истории сделок
        trades = await self.bot.data_manager.get_trade_history(days=90)

        if not trades:
            self.console.print("[yellow]Нет данных о производительности[/yellow]")
            await asyncio.sleep(1)
            return

        # Создание таблицы метрик
        metrics_table = Table(title="Метрики производительности")
        metrics_table.add_column("Метрика")
        metrics_table.add_column("Значение", justify="right")

        for name, value in metrics.items():
            if isinstance(value, float):
                value_str = f"{value:.2f}"
            else:
                value_str = str(value)

            color = "green" if (name == "total_profit_loss" and value > 0) else (
                "red" if (name == "total_profit_loss" and value < 0) else ""
            )

            metrics_table.add_row(
                name.replace("_", " ").title(),
                f"[{color}]{value_str}[/{color}]",
            )

        # Создание таблицы распределения
        winning_trades = [t for t in trades if t.get("profit", 0) > 0]
        losing_trades = [t for t in trades if t.get("profit", 0) < 0]

        dist_table = Table(title="Распределение сделок")
        dist_table.add_column("Категория")
        dist_table.add_column("Количество", justify="right")
        dist_table.add_column("Ср. P/L", justify="right")
        dist_table.add_column("Общий P/L", justify="right")

        dist_table.add_row(
            "Успешные сделки",
            str(len(winning_trades)),
            f"{sum(t.get('profit', 0) for t in winning_trades) / len(winning_trades) if winning_trades else 0:.2f}",
            f"{sum(t.get('profit', 0) for t in winning_trades):.2f}",
        )

        dist_table.add_row(
            "Убыточные сделки",
            str(len(losing_trades)),
            f"{sum(t.get('profit', 0) for t in losing_trades) / len(losing_trades) if losing_trades else 0:.2f}",
            f"{sum(t.get('profit', 0) for t in losing_trades):.2f}",
        )

        dist_table.add_row(
            "Все сделки",
            str(len(trades)),
            f"{sum(t.get('profit', 0) for t in trades) / len(trades) if trades else 0:.2f}",
            f"{sum(t.get('profit', 0) for t in trades):.2f}",
        )

        self.console.print(metrics_table)
        self.console.print(dist_table)

        # TODO: Добавить визуализацию графиков здесь
        self.console.print("\n[blue]Здесь будет отображаться визуализация графиков[/blue]")

        await questionary.press_any_key_to_continue().ask_async()

    async def _show_market_data(self):
        """Отображение рыночных данных."""
        instruments = list(self.bot.api.instruments.values())
        instrument_names = [f"{i.name} ({i.figi})" for i in instruments]

        instrument_choice = await questionary.select(
            "Выберите инструмент для просмотра:",
            choices=instrument_names,
        ).ask_async()

        figi = instruments[instrument_names.index(instrument_choice)].figi

        # Получение исторических данных
        historical_data = self.bot.data_manager.historical_data.get(figi)

        if not historical_data:
            self.console.print("[yellow]Нет исторических данных для этого инструмента[/yellow]")
            await asyncio.sleep(1)
            return

        # Отображение последних 10 свечей
        table = Table(title=f"Последние рыночные данные для {instrument_choice}")
        table.add_column("Время")
        table.add_column("Open", justify="right")
        table.add_column("High", justify="right")
        table.add_column("Low", justify="right")
        table.add_column("Close", justify="right")
        table.add_column("Volume", justify="right")

        for _, row in historical_data.tail(10).iterrows():
            table.add_row(
                str(row.name),
                f"{row['open']:.4f}",
                f"{row['high']:.4f}",
                f"{row['low']:.4f}",
                f"{row['close']:.4f}",
                f"{row['volume']:,}",
            )

        self.console.print(table)

        # TODO: Добавить визуализацию графика здесь
        self.console.print("\n[blue]Здесь будет отображаться график цен[/blue]")

        await questionary.press_any_key_to_continue().ask_async()

    async def _configuration_menu(self):
        """Меню настроек конфигурации."""
        while self._running:
            try:
                choices = [
                    "Switch Environment (Sandbox/Production)",
                    "Set Risk Parameters",
                    "API Connection Test",
                    "Back to Main Menu",
                ]

                choice = await questionary.select(
                    "Опции конфигурации:",
                    choices=choices,
                ).ask_async()

                if choice == "Switch Environment (Sandbox/Production)":
                    await self._switch_environment()
                elif choice == "Set Risk Parameters":
                    await self._set_risk_parameters()
                elif choice == "API Connection Test":
                    await self._test_api_connection()
                elif choice == "Back to Main Menu":
                    return

            except KeyboardInterrupt:
                return
            except Exception as e:
                self.console.print(f"[red]Ошибка: {e}[/red]")
                await asyncio.sleep(1)

    async def _switch_environment(self):
        """Переключение между песочницей и рабочим окружением."""
        current_env = self.bot.config.environment
        new_env = "production" if current_env == "sandbox" else "sandbox"

        confirm = await questionary.confirm(
            f"Переключиться с {current_env} на {new_env} окружение? "
            "Это потребует перезапуска."
        ).ask_async()

        if confirm:
            self.bot.config.environment = new_env
            await self.bot.config.save()

            self.console.print(
                f"[green]Окружение переключено на {new_env}. "
                "Пожалуйста, перезапустите приложение.[/green]"
            )

            self._running = False
            await asyncio.sleep(2)

    async def _set_risk_parameters(self):
        """Установка параметров управления рисками."""
        risk = await questionary.text(
            "Введите риск на сделку (в процентах, текущее: "
            f"{self.bot.config.risk_per_trade*100:.1f}%):",
            validate=lambda x: x.replace(".", "", 1).isdigit() and 0 < float(x) <= 100,
        ).ask_async()

        max_trades = await questionary.text(
            "Введите максимальное количество открытых сделок (текущее: "
            f"{self.bot.config.max_open_trades}):",
            validate=lambda x: x.isdigit() and int(x) > 0,
        ).ask_async()

        confirm = await questionary.confirm(
            f"Установить риск на сделку {float(risk):.1f}% и "
            f"максимальное количество открытых сделок {int(max_trades)}?"
        ).ask_async()

        if confirm:
            self.bot.config.risk_per_trade = float(risk) / 100
            self.bot.config.max_open_trades = int(max_trades)
            await self.bot.config.save()

            self.console.print("[green]Параметры риска успешно обновлены![/green]")
            await asyncio.sleep(1)

    async def _test_api_connection(self):
        """Тестирование подключения к Tinkoff API."""
        with self.console.status("[bold green]Тестирование подключения к API..."):
            success = await TinkoffAPI.test_connection(self.bot.config)

            if success:
                self.console.print("[green]Тест подключения к API успешен![/green]")
            else:
                self.console.print("[red]Тест подключения к API не удался![/red]")

            await asyncio.sleep(2)

    def _update_footer(self):
        """Обновление footer с текущим статусом."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        env = self.bot.config.environment.capitalize()

        footer_text = Text(f"Статус: Работает | Окружение: {env} | {now}", justify="center")
        self.layout["footer"].update(footer_text)
