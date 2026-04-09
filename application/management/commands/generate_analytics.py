from django.core.management.base import BaseCommand
import json
import os
from django.conf import settings
from application.services.analytics_service import run_analytics_pipeline

class Command(BaseCommand):
    help = 'Генерация аналитики студентов на основе данных из БД'

    def handle(self, *args, **options):
        self.stdout.write('Запуск аналитики...')
        
        try:
            # Запуск логики
            results = run_analytics_pipeline()
            
            if "error" in results:
                self.stdout.write(self.style.ERROR(f"Ошибка: {results['error']}"))
                return

            # Сохранение результата в JSON файл 
            cache_dir = os.path.join(settings.MEDIA_ROOT, 'analytics_cache')
            file_path = os.path.join(cache_dir, 'student_analytics.json')
            
            if not os.path.exists(cache_dir):
                os.makedirs(cache_dir)
                self.stdout.write(f'Создана директория: {cache_dir}')

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            
            self.stdout.write(self.style.SUCCESS(f'Аналитика успешно сохранена в {file_path}'))
            self.stdout.write(f'Обработано студентов: {results["total_students"]}')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Критическая ошибка: {str(e)}'))
            raise