from django.core.management.base import BaseCommand
from application.services.grade_prediction_service import run_prediction_pipeline

class Command(BaseCommand):
    """
    Management команда для запуска процесса нейросетевого прогнозирования оценок.
    
    Назначение:
    - Инициирует пайплайн машинного обучения (PyTorch) для предсказания будущей успеваемости студентов.
    - Использует данные старших курсов для обучения модели и прогнозирует оценки для указанного курса.
    - Сохраняет результаты в JSON-файл в кэше (`media/prediction_cache/`).
    
    Использование через консоль:
        python manage.py generate_grade_predictions --faculty="Название факультета" --group-base="ИСТб" --course=2

    Зависимости:
    - Сервис `application.services.grade_prediction_service.run_prediction_pipeline`.
    - Наличие данных в БД (студенты, оценки, посещаемость) для выбранного факультета и группы.
    - Установленные библиотеки: torch, pandas, scikit-learn.
    """
    help = 'Запуск нейросетевого прогнозирования оценок для указанной группы и курса'

    def add_arguments(self, parser):
        """
        Определяет аргументы командной строки для команды.
        
        Args:
            parser (argparse.ArgumentParser): Парсер аргументов Django.
            
        Добавляемые аргументы:
            --faculty (str): Полное название факультета (обязательно). 
                             Должно точно совпадать с записью в БД.
            --group-base (str): Базовая часть названия группы без года и дефиса (обязательно).
                                Например, "ИСТб" для групп "ИСТб-21", "ИСТб-22".
            --course (int): Номер курса, для которого требуется сделать прогноз (обязательно).
                            Допустимые значения: 1, 2, 3. 
                            Прогноз для 4 курса невозможен из-за отсутствия старших курсов для обучения.
        """
        parser.add_argument('--faculty', type=str, required=True, help='Название факультета')
        parser.add_argument('--group-base', type=str, required=True, help='База названия группы (напр. ИСТб)')
        parser.add_argument('--course', type=int, required=True, help='Курс для предсказания (1, 2, 3)')

    def handle(self, *args, **options):
        """
        Основной метод выполнения команды.
        
        Логика работы:
        1. Извлекает параметры из аргументов командной строки.
        2. Выводит сообщение о начале процесса в stdout.
        3. Вызывает сервис `run_prediction_pipeline` для выполнения ML-задач:
           - Сбор и подготовка данных из БД.
           - Обучение нейросети GradeRegressor.
           - Генерация прогнозов.
           - Сохранение результатов в JSON.
        4. Обрабатывает результат
           
        Args:
            **options: Словарь аргументов (faculty, group_base, course).
        """
        faculty = options['faculty']
        group_base = options['group_base']
        course = options['course']
        
        self.stdout.write(f'Запуск прогнозирования для {faculty}, {group_base}, курс {course}...')
        
        result = run_prediction_pipeline(faculty, group_base, course)
        
        if 'error' in result:
            self.stdout.write(self.style.ERROR(f"Ошибка: {result['error']}"))
        else:
            self.stdout.write(self.style.SUCCESS(result['message']))
            self.stdout.write(f"Сгенерировано прогнозов: {result['count']}")
            self.stdout.write(f"Файл сохранен: {result['file']}")