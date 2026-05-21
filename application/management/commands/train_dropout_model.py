# application/management/commands/train_dropout_model.py
from django.core.management.base import BaseCommand
from application.models import Student, StudentResult, Attendance
from application.ml_model import dropout_risk_model
from application.services.student_rating_service import StudentRatingService
import random

class Command(BaseCommand):
    help = 'Обучает ML модель для предсказания риска отчисления'
    
    def handle(self, *args, **options):
        self.stdout.write("Начало обучения ML модели...")
        
        # 1. Собираем исторические данные
        training_data = []
        labels = []
        
        students = Student.objects.filter(is_academic=False)
        
        for student in students:
            # Собираем признаки для каждого студента
            student_data = self._collect_student_features(student)
            
            # Определяем метку (отчислен или нет)
            # Для реальных данных нужно брать из истории
            is_dropped_out = self._get_dropout_label(student)
            
            training_data.append(student_data)
            labels.append(1 if is_dropped_out else 0)
        
        if len(training_data) < 10:
            # Если мало реальных данных, генерируем синтетические
            self.stdout.write("Мало реальных данных, генерирую синтетические...")
            training_data, labels = self._generate_synthetic_data()
        
        # 2. Обучаем модель
        result = dropout_risk_model.train_model(training_data, labels)
        
        self.stdout.write(self.style.SUCCESS(
            f"Модель обучена!\n"
            f"Accuracy: {result['accuracy']:.3f}\n"
            f"ROC-AUC: {result['roc_auc']:.3f}"
        ))
        
        # Выводим важность признаков
        importance = dropout_risk_model.get_feature_importance()
        self.stdout.write("\nВажность признаков:")
        for feature, imp in importance.items():
            self.stdout.write(f"  {feature}: {imp:.3f}")
    
    def _collect_student_features(self, student):
        """Собирает признаки студента"""
        # Расчет среднего балла
        results = StudentResult.objects.filter(student=student)
        numeric_grades = []
        debt_count = 0
        
        for res in results:
            val = res.result.result_value
            if val in ['2', 'Н/Я', 'Не зачтено']:
                debt_count += 1
            norm = StudentRatingService.normalize_grade_value(val)
            if norm:
                numeric_grades.append(norm)
        
        avg_grade = sum(numeric_grades) / len(numeric_grades) if numeric_grades else 0
        
        # Расчет посещаемости
        attendance_percent = StudentRatingService.calculate_attendance_percent(student.student_id)
        
        # Расчет доли долгов
        total_subjects = results.count()
        debt_ratio = debt_count / total_subjects if total_subjects > 0 else 0
        
        # Курс
        course = 1
        if student.group and student.group.name:
            year = StudentRatingService.extract_year_from_group_name(student.group.name)
            if year:
                course = StudentRatingService.calculate_course(year)
        
        return {
            'avg_grade': avg_grade,
            'attendance_percent': attendance_percent,
            'debt_count': debt_count,
            'total_subjects': total_subjects,
            'debt_ratio': debt_ratio,
            'grade_trend': 0,  # Можно рассчитать тренд по семестрам
            'course': course,
            'semester_debts': debt_count
        }
    
    def _get_dropout_label(self, student):
        """
        Определяет, отчислился ли студент.
        В реальности - нужно брать из истории.
        """
        # Для демо - случайно
        return random.random() < 0.1
    
    def _generate_synthetic_data(self):
        """Генерирует синтетические данные для обучения"""
        training_data = []
        labels = []
        
        patterns = [
            # Отличники (низкий риск)
            ({'avg_grade': 4.8, 'attendance_percent': 95, 'debt_count': 0, 'total_subjects': 10, 'debt_ratio': 0, 'grade_trend': 0.1, 'course': 3, 'semester_debts': 0}, 0),
            ({'avg_grade': 4.5, 'attendance_percent': 90, 'debt_count': 0, 'total_subjects': 10, 'debt_ratio': 0, 'grade_trend': 0.05, 'course': 2, 'semester_debts': 0}, 0),
            ({'avg_grade': 4.2, 'attendance_percent': 85, 'debt_count': 0, 'total_subjects': 10, 'debt_ratio': 0, 'grade_trend': 0, 'course': 1, 'semester_debts': 0}, 0),
            
            # Хорошисты (низкий-средний риск)
            ({'avg_grade': 3.8, 'attendance_percent': 80, 'debt_count': 0, 'total_subjects': 10, 'debt_ratio': 0, 'grade_trend': -0.05, 'course': 2, 'semester_debts': 0}, 0),
            ({'avg_grade': 3.5, 'attendance_percent': 75, 'debt_count': 0, 'total_subjects': 10, 'debt_ratio': 0, 'grade_trend': -0.1, 'course': 3, 'semester_debts': 0}, 0),
            
            # Троечники (средний риск)
            ({'avg_grade': 3.2, 'attendance_percent': 70, 'debt_count': 1, 'total_subjects': 10, 'debt_ratio': 0.1, 'grade_trend': -0.15, 'course': 2, 'semester_debts': 1}, 0),
            ({'avg_grade': 3.0, 'attendance_percent': 60, 'debt_count': 1, 'total_subjects': 10, 'debt_ratio': 0.1, 'grade_trend': -0.2, 'course': 1, 'semester_debts': 1}, 1),
            
            # Должники (высокий риск)
            ({'avg_grade': 2.8, 'attendance_percent': 50, 'debt_count': 2, 'total_subjects': 10, 'debt_ratio': 0.2, 'grade_trend': -0.3, 'course': 2, 'semester_debts': 2}, 1),
            ({'avg_grade': 2.5, 'attendance_percent': 40, 'debt_count': 3, 'total_subjects': 10, 'debt_ratio': 0.3, 'grade_trend': -0.4, 'course': 3, 'semester_debts': 3}, 1),
            ({'avg_grade': 2.0, 'attendance_percent': 30, 'debt_count': 4, 'total_subjects': 10, 'debt_ratio': 0.4, 'grade_trend': -0.5, 'course': 1, 'semester_debts': 4}, 1),
            
            # Прогульщики (высокий риск)
            ({'avg_grade': 3.0, 'attendance_percent': 35, 'debt_count': 2, 'total_subjects': 10, 'debt_ratio': 0.2, 'grade_trend': -0.25, 'course': 2, 'semester_debts': 2}, 1),
            ({'avg_grade': 2.7, 'attendance_percent': 25, 'debt_count': 3, 'total_subjects': 10, 'debt_ratio': 0.3, 'grade_trend': -0.35, 'course': 1, 'semester_debts': 3}, 1),
        ]
        
        # Генерируем больше данных с небольшими вариациями
        for _ in range(100):
            for pattern, label in patterns:
                data = pattern.copy()
                # Добавляем случайный шум
                data['avg_grade'] = max(2.0, min(5.0, data['avg_grade'] + random.uniform(-0.3, 0.3)))
                data['attendance_percent'] = max(0, min(100, data['attendance_percent'] + random.uniform(-10, 10)))
                training_data.append(data)
                labels.append(label)
        
        return training_data, labels