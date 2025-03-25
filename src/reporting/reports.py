# Генератор отчетов
class ReportGenerator:
    def generate_daily_report(self, trades):
        """Генерация ежедневного отчета в CSV"""
        df = pd.DataFrame(trades)  # Создание DataFrame из сделок
        filename = f"daily_report_{datetime.datetime.now().date()}.csv"
        df.to_csv(os.path.join(REPORTS_DIR, filename))  # Сохранение в файл

    def generate_monthly_report(self):
        """Заглушка для ежемесячного отчета (требует реализации)"""
        pass