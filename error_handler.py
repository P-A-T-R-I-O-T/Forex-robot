import logging
from datetime import datetime
from typing import Optional


class ErrorHandler:
    """
    Класс для обработки ошибок и логирования в Forex-robot.
    Обеспечивает запись ошибок в лог-файл и при необходимости отправку уведомлений.
    """

    def __init__(self, log_file: str = 'forex_robot_errors.log'):
        """
        Инициализация обработчика ошибок.

        :param log_file: Путь к файлу для записи логов
        """
        self.log_file = log_file
        self.setup_logging()

    def setup_logging(self) -> None:
        """Настройка системы логирования."""
        logging.basicConfig(
            level=logging.ERROR,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('ForexRobot')

    def log_error(self, error: Exception, context: Optional[str] = None) -> None:
        """
        Логирование ошибки с дополнительным контекстом.

        :param error: Объект исключения
        :param context: Дополнительная информация о контексте ошибки
        """
        error_message = f"Error: {str(error)}"
        if context:
            error_message += f" | Context: {context}"

        self.logger.error(error_message)

    def critical_error(self, error: Exception, stop_robot: bool = False) -> None:
        """
        Обработка критической ошибки с возможностью остановки робота.

        :param error: Объект исключения
        :param stop_robot: Флаг, указывающий на необходимость остановки робота
        """
        self.log_error(error, "CRITICAL ERROR")
        if stop_robot:
            self.logger.error("Stopping the robot due to critical error")
            # Здесь можно добавить логику для безопасной остановки робота

    def get_error_report(self) -> str:
        """
        Генерация отчёта об ошибках за текущий день.

        :return: Строка с отчётом об ошибках
        """
        try:
            with open(self.log_file, 'r') as f:
                today = datetime.now().strftime('%Y-%m-%d')
                errors = [line for line in f.readlines() if today in line]
                return "\n".join(errors) if errors else "No errors today"
        except FileNotFoundError:
            return "No error log file found"


# Создаём глобальный экземпляр обработчика ошибок для использования в других модулях
error_handler = ErrorHandler()