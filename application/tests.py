"""
Тесты для Django проекта IRNTU Dashboard

Тестирует:
- Утилиты для работы со студентами (student_utils)
- Сервисы аналитики (GradeStatisticsService, StudentRatingService и др.)
- API эндпоинты (ViewSet'ы)
- Management команды
"""

import pytest
from datetime import datetime
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock
from model_bakery import baker

from application.utils.student_utils import (
    extract_year_from_group_name,
    calculate_course,
    student_is_still_enrolled
)
from application.services.grade_statistics_service import GradeStatisticsService
from application.services.student_rating_service import StudentRatingService
from application.services.academic_performance_service import AcademicPerformanceService
from application.services.subject_statistics_service import SubjectStatisticsService
from application.models import (
    Faculty, Speciality, StudentGroup, Student,
    Discipline, ResultType, StudentResult, Attendance, Administrator
)


# ============================================================
# ЧАСТЬ 1: ТЕСТЫ УТИЛИТ (student_utils.py)
# ============================================================

class TestStudentUtils(TestCase):
    """Тесты для вспомогательных функций работы со студентами"""
    
    def test_extract_year_from_group_name_valid(self):
        """Тест корректного извлечения года из названия группы"""
        test_cases = [
            ("КСм-23", 2023),
            ("ИТСб-21", 2021),
            ("АСУб-22", 2022),
            ("ЭБ-20", 2020),
            ("ФИТ-19", 2019),
        ]
        
        for group_name, expected_year in test_cases:
            with self.subTest(group_name=group_name):
                result = extract_year_from_group_name(group_name)
                self.assertEqual(result, expected_year)
    
    def test_extract_year_from_group_name_invalid(self):
        """Тест обработки некорректных названий групп"""
        test_cases = [
            ("", None),
            (None, None),
            ("Без-дефиса-но-много-частей", None),
            ("ФИТ", None),
            ("ФИТ-", None),
            ("-23", None),
            ("invalid", None),
        ]
        
        for group_name, expected in test_cases:
            with self.subTest(group_name=group_name):
                result = extract_year_from_group_name(group_name)
                self.assertEqual(result, expected)
    
    @patch('application.utils.student_utils.datetime')
    def test_calculate_course_before_september(self, mock_datetime):
        """Тест расчета курса до сентября (еще старый курс)"""
        # 31 августа 2024
        mock_datetime.now.return_value = datetime(2024, 8, 31)
        
        # Поступил в 2021 -> должен быть на 3 курсе (2024-2021=3)
        self.assertEqual(calculate_course(2021), 3)
        
        # Поступил в 2022 -> 2 курс
        self.assertEqual(calculate_course(2022), 2)
    
    @patch('application.utils.student_utils.datetime')
    def test_calculate_course_after_september(self, mock_datetime):
        """Тест расчета курса после сентября (уже новый курс)"""
        # 1 сентября 2024
        mock_datetime.now.return_value = datetime(2024, 9, 1)
        
        # Поступил в 2021 -> должен быть на 4 курсе (2024-2021+1=4)
        self.assertEqual(calculate_course(2021), 4)
        
        # Поступил в 2022 -> 3 курс
        self.assertEqual(calculate_course(2022), 3)
    
    @patch('application.utils.student_utils.datetime')
    def test_calculate_course_december(self, mock_datetime):
        """Тест расчета курса в декабре"""
        mock_datetime.now.return_value = datetime(2024, 12, 25)
        
        self.assertEqual(calculate_course(2021), 4)
        self.assertEqual(calculate_course(2022), 3)
    
    @patch('application.utils.student_utils.datetime')
    def test_student_is_still_enrolled(self, mock_datetime):
        """Тест проверки, учится ли студент еще"""
        
        # Случай 1: Еще не закончил (2024 год, выпуск 2025)
        mock_datetime.now.return_value = datetime(2024, 6, 15)
        self.assertTrue(student_is_still_enrolled(2021))
        
        # Случай 2: Год выпуска, но до июля
        mock_datetime.now.return_value = datetime(2025, 6, 30)
        self.assertTrue(student_is_still_enrolled(2021))
        
        # Случай 3: Год выпуска, после июля
        mock_datetime.now.return_value = datetime(2025, 7, 1)
        self.assertFalse(student_is_still_enrolled(2021))
        
        # Случай 4: Уже закончил
        mock_datetime.now.return_value = datetime(2026, 1, 15)
        self.assertFalse(student_is_still_enrolled(2021))


# ============================================================
# ЧАСТЬ 2: ТЕСТЫ СЕРВИСОВ
# ============================================================

class TestGradeStatisticsService(TestCase):
    """Тесты для сервиса статистики оценок"""
    
    def test_normalize_grade_numeric(self):
        """Тест нормализации числовых оценок"""
        self.assertEqual(GradeStatisticsService.normalize_grade("5"), "5")
        self.assertEqual(GradeStatisticsService.normalize_grade("4"), "4")
        self.assertEqual(GradeStatisticsService.normalize_grade("3"), "3")
        self.assertEqual(GradeStatisticsService.normalize_grade("2"), "2")
    
    def test_normalize_grade_text(self):
        """Тест нормализации текстовых оценок"""
        self.assertEqual(GradeStatisticsService.normalize_grade("Зачтено"), "зачет")
        self.assertEqual(GradeStatisticsService.normalize_grade("Не зачтено"), "незачет")
        self.assertEqual(GradeStatisticsService.normalize_grade("Н/Я"), "неявка")
    
    def test_normalize_grade_edge_cases(self):
        """Тест граничных случаев"""
        self.assertEqual(GradeStatisticsService.normalize_grade(""), "Не указано")
        self.assertEqual(GradeStatisticsService.normalize_grade(None), "Не указано")
        self.assertEqual(GradeStatisticsService.normalize_grade("Неизвестно"), "Неизвестно")
    
    def test_update_grade_stats(self):
        """Тест обновления статистики оценок"""
        stats = {
            'numeric_grades': [],
            'countGrade2': 0, 'countGrade3': 0,
            'countGrade4': 0, 'countGrade5': 0,
            'countZachet': 0, 'countNejavka': 0, 'countNezachet': 0
        }
        
        # Тестируем числовые оценки
        GradeStatisticsService.update_grade_stats(stats, "5")
        self.assertEqual(stats['countGrade5'], 1)
        self.assertEqual(stats['numeric_grades'], [5])
        
        GradeStatisticsService.update_grade_stats(stats, "4")
        self.assertEqual(stats['countGrade4'], 1)
        self.assertEqual(stats['numeric_grades'], [5, 4])
        
        # Тестируем зачет/незачет
        GradeStatisticsService.update_grade_stats(stats, "зачет")
        self.assertEqual(stats['countZachet'], 1)
        
        GradeStatisticsService.update_grade_stats(stats, "незачет")
        self.assertEqual(stats['countNezachet'], 1)
        
        GradeStatisticsService.update_grade_stats(stats, "неявка")
        self.assertEqual(stats['countNejavka'], 1)


class TestStudentRatingService(TestCase):
    """Тесты для сервиса рейтинга студентов"""
    
    def test_classify_debt_type(self):
        """Тест классификации типов долгов"""
        test_cases = [
            ("2", "неуд"),
            ("Н/Я", "неявка"),
            ("Не зачтено", "незачет"),
            ("", "другой"),
            (None, "другой"),
            ("Что-то странное", "другой"),
        ]
        
        for grade_value, expected in test_cases:
            with self.subTest(grade_value=grade_value):
                result = StudentRatingService.classify_debt_type(grade_value)
                self.assertEqual(result, expected)
    
    def test_get_risk_level(self):
        """Тест определения уровня риска"""
        test_cases = [
            (0.0, "низкий"),
            (0.1, "низкий"),
            (0.29, "низкий"),
            (0.3, "средний"),
            (0.5, "средний"),
            (0.69, "средний"),
            (0.7, "высокий"),
            (0.9, "высокий"),
            (1.0, "высокий"),
        ]
        
        for risk_score, expected_level in test_cases:
            with self.subTest(risk_score=risk_score):
                result = StudentRatingService.get_risk_level(risk_score)
                self.assertEqual(result, expected_level)
    
    def test_calculate_dropout_risk_formula(self):
        """Тест формулы расчета риска отчисления"""
        # Мокаем долги
        with patch('application.services.student_rating_service.StudentResult.objects') as mock_result:
            mock_result.filter.return_value.count.return_value = 0  # нет долгов
            
            # Студент с отличными показателями
            risk = StudentRatingService.calculate_dropout_risk(
                student_id=1,
                avg_grade=4.8,
                attendance_percent=95.0,
                activity=4.5
            )
            self.assertLess(risk, 0.3)  # риск должен быть низким
            
            # Мокаем долги (2 долга)
            mock_result.filter.return_value.count.return_value = 2
            
            risk = StudentRatingService.calculate_dropout_risk(
                student_id=1,
                avg_grade=2.5,
                attendance_percent=30.0,
                activity=1.5
            )
            self.assertGreater(risk, 0.5)  # риск должен быть высоким
            self.assertLessEqual(risk, 1.0)  # но не больше 1


class TestAcademicPerformanceService(TestCase):
    """Тесты для сервиса академической успеваемости"""
    
    def test_get_debts_filter(self):
        """Тест фильтра задолженностей"""
        debts_filter = AcademicPerformanceService.get_debts_filter()
        
        # Проверяем, что фильтр содержит правильные условия
        filter_str = str(debts_filter)
        self.assertTrue(
            '2' in filter_str or 
            'Н/Я' in filter_str or 
            'Не зачтено' in filter_str
        )
    
    def test_get_debt_distribution(self):
        """Тест распределения задолженностей"""
        # Создаем мок-студентов с разным количеством долгов
        class MockStudent:
            def __init__(self, debt_count):
                self.debt_count = debt_count
        
        students = [
            MockStudent(0), MockStudent(0), MockStudent(0),  # 3 студента без долгов
            MockStudent(1),  # 1 студент с 1 долгом
            MockStudent(2), MockStudent(2),  # 2 студента с 2 долгами
            MockStudent(3), MockStudent(4),  # 2 студента с 3+ долгами
        ]
        
        distribution = AcademicPerformanceService.get_debt_distribution(students)
        
        self.assertEqual(distribution['zero_debts'], 3)
        self.assertEqual(distribution['one_debt'], 1)
        self.assertEqual(distribution['two_debts'], 2)
        self.assertEqual(distribution['three_plus_debts'], 2)
    
    def test_calculate_group_stats_empty(self):
        """Тест расчета статистики по группам с пустыми данными"""
        stats = AcademicPerformanceService.calculate_group_stats([])
        self.assertEqual(stats, [])


class TestSubjectStatisticsService(TestCase):
    """Тесты для сервиса статистики по предметам"""
    
    def test_normalize_grade_value(self):
        """Тест нормализации значений оценок"""
        test_cases = [
            ("5", 5),
            ("4", 4),
            ("3", 3),
            ("2", 2),
            ("Зачтено", "зачет"),
            ("Не зачтено", "незачет"),
            ("Н/Я", "неявка"),
            ("", None),
            (None, None),
            ("6", None),
            ("1", None),
        ]
        
        for input_val, expected in test_cases:
            with self.subTest(input_val=input_val):
                result = SubjectStatisticsService.normalize_grade_value(input_val)
                self.assertEqual(result, expected)
    
    def test_calculate_activity_for_discipline(self):
        """Тест расчета активности по предмету"""
        # Идеальный предмет
        activity = SubjectStatisticsService.calculate_activity_for_discipline(
            avg_grade=5.0,
            attendance_percent=100.0,
            debt_ratio=0.0
        )
        self.assertAlmostEqual(activity, 5.0, places=1)
        
        # Плохой предмет
        activity = SubjectStatisticsService.calculate_activity_for_discipline(
            avg_grade=2.5,
            attendance_percent=30.0,
            debt_ratio=0.8
        )
        self.assertLess(activity, 3.0)
        
        # Граничный случай
        activity = SubjectStatisticsService.calculate_activity_for_discipline(
            avg_grade=0,
            attendance_percent=0,
            debt_ratio=1.0
        )
        self.assertGreaterEqual(activity, 0)
        self.assertLessEqual(activity, 5.0)
    
    def test_empty_response(self):
        """Тест пустого ответа"""
        empty_response = SubjectStatisticsService._empty_response()
        
        self.assertIn('subjectStats', empty_response)
        self.assertIn('gradeDistributionBar', empty_response)
        self.assertIn('bestSubjects', empty_response)
        self.assertEqual(empty_response['bestSubjects'], [])
        self.assertEqual(empty_response['gradeDistributionBar']['2'], 0)


# ============================================================
# ЧАСТЬ 3: API ТЕСТЫ (интеграционные)
# ============================================================

class TestAuthenticationAPI(APITestCase):
    """Тесты эндпоинтов аутентификации"""
    
    def setUp(self):
        self.client = APIClient()
        self.register_url = reverse('register')
        self.login_url = reverse('login')
        
        # Создаем тестового админа
        self.admin_data = {
            'email': 'admin@test.com',
            'name': 'Test Admin',
            'password': 'testpass123'
        }
    
    def test_register_success(self):
        """Тест успешной регистрации"""
        response = self.client.post(self.register_url, self.admin_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['message'], 'Administrator created successfully!')
        
        # Проверяем, что пользователь создался
        self.assertTrue(Administrator.objects.filter(email='admin@test.com').exists())
    
    def test_register_duplicate_email(self):
        """Тест регистрации с существующим email"""
        # Создаем пользователя
        Administrator.objects.create_user(
            email='admin@test.com',
            password='testpass123',
            name='Test Admin'
        )
        
        # Пытаемся создать дубликат
        response = self.client.post(self.register_url, self.admin_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_login_success(self):
        """Тест успешного входа"""
        # Сначала регистрируем пользователя
        self.client.post(self.register_url, self.admin_data, format='json')
        
        # Пытаемся войти
        login_data = {
            'email': 'admin@test.com',
            'password': 'testpass123'
        }
        response = self.client.post(self.login_url, login_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        
        # Проверяем, что cookie установлена
        self.assertIn('access_token', response.cookies)
    
    def test_login_wrong_password(self):
        """Тест входа с неверным паролем"""
        # Создаем пользователя
        Administrator.objects.create_user(
            email='admin@test.com',
            password='testpass123',
            name='Test Admin'
        )
        
        login_data = {
            'email': 'admin@test.com',
            'password': 'wrongpassword'
        }
        response = self.client.post(self.login_url, login_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data['error'], 'Неверные данные')


class TestStatisticsAPI(APITestCase):
    """Тесты API статистики (требуют аутентификации)"""
    
    def setUp(self):
        self.client = APIClient()
        
        # Создаем и аутентифицируем админа
        self.admin = Administrator.objects.create_user(
            email='admin@test.com',
            password='testpass123',
            name='Test Admin',
            is_staff=True
        )
        self.client.force_authenticate(user=self.admin)
        
        # Создаем тестовые данные
        self._create_test_data()
    
    def _create_test_data(self):
        """Создание тестовых данных в БД"""
        # Факультет
        self.faculty = Faculty.objects.create(
            faculty_id=1,
            name='Институт информационных технологий'
        )
        
        # Специальность
        self.speciality = Speciality.objects.create(
            speciality_id=1,
            name='Информационные системы',
            faculty=self.faculty
        )
        
        # Группа
        self.group = StudentGroup.objects.create(
            group_id=1,
            name='ИСТб-21',
            speciality=self.speciality
        )
        
        # Студент
        self.student = Student.objects.create(
            student_id=12345,
            birthday='2000-01-01',
            is_academic=False,
            group=self.group
        )
        
        # Дисциплина
        self.discipline = Discipline.objects.create(
            discipline_id=1,
            name='Программирование'
        )
        
        # Тип результата
        self.result_type = ResultType.objects.create(
            result_id=5,
            result_value='5'
        )
        
        # Результат студента
        self.student_result = StudentResult.objects.create(
            student=self.student,
            discipline=self.discipline,
            result=self.result_type
        )
    
    def test_grades_statistics_endpoint(self):
        """Тест эндпоинта статистики оценок"""
        url = reverse('api-grades-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('summary', response.data)
        self.assertIn('students', response.data)
        self.assertIn('subjects', response.data)
    
    def test_grades_statistics_with_filters(self):
        """Тест эндпоинта статистики оценок с фильтрами"""
        url = reverse('api-grades-list')
        
        # Фильтр по группе
        response = self.client.get(url, {'group': 'ИСТб-21'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Фильтр по предмету
        response = self.client.get(url, {'subject': 'Программирование'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_subject_statistics_endpoint(self):
        """Тест эндпоинта статистики по предметам"""
        url = reverse('subject-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('subjectStats', response.data)
        self.assertIn('gradeDistributionBar', response.data)
        self.assertIn('bestSubjects', response.data)
    
    def test_subject_statistics_with_sorting(self):
        """Тест эндпоинта с сортировкой"""
        url = reverse('subject-list')
        
        # Сортировка по среднему баллу
        response = self.client.get(url, {'sortBy': 'avg', 'limit': 5})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Сортировка по активности
        response = self.client.get(url, {'sortBy': 'activity', 'limit': 10})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_academic_performance_endpoint(self):
        """Тест эндпоинта академической успеваемости"""
        url = reverse('performance-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('debtsDistribution', response.data)
        self.assertIn('groupAverages', response.data)
        self.assertIn('students', response.data)
    
    def test_student_rating_endpoint(self):
        """Тест эндпоинта рейтинга студентов"""
        url = reverse('api-rating-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('chartData', response.data)
        self.assertIn('students', response.data)
    
    def test_student_rating_with_limit(self):
        """Тест эндпоинта рейтинга с ограничением"""
        url = reverse('api-rating-list')
        response = self.client.get(url, {'limit': 5, 'sortBy': 'rating'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertLessEqual(len(response.data['students']), 5)


class TestUnauthorizedAccess(APITestCase):
    """Тесты доступа без аутентификации"""
    
    def setUp(self):
        self.client = APIClient()
    
    def test_statistics_endpoints_require_auth(self):
        """Тест, что эндпоинты статистики требуют аутентификации"""
        endpoints = [
            reverse('api-grades-list'),
            reverse('subject-list'),
            reverse('performance-list'),
            reverse('api-rating-list'),
        ]
        
        for url in endpoints:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


# ============================================================
# ЧАСТЬ 4: ТЕСТЫ МОДЕЛЕЙ
# ============================================================

class TestModels(TestCase):
    """Тесты моделей данных"""
    
    def setUp(self):
        self.faculty = Faculty.objects.create(
            faculty_id=1,
            name='Тестовый факультет'
        )
        
        self.speciality = Speciality.objects.create(
            speciality_id=1,
            name='Тестовая специальность',
            faculty=self.faculty
        )
        
        self.group = StudentGroup.objects.create(
            group_id=1,
            name='ТЕСТ-21',
            speciality=self.speciality
        )
        
        self.student = Student.objects.create(
            student_id=123,
            birthday='2000-01-01',
            is_academic=False,
            group=self.group
        )
        
        self.discipline = Discipline.objects.create(
            discipline_id=1,
            name='Тестовая дисциплина'
        )
        
        self.result_type = ResultType.objects.create(
            result_id=5,
            result_value='5'
        )
    
    def test_faculty_str(self):
        """Тест строкового представления факультета"""
        self.assertEqual(str(self.faculty), 'Тестовый факультет')
    
    def test_speciality_str(self):
        """Тест строкового представления специальности"""
        self.assertEqual(str(self.speciality), 'Тестовая специальность')
    
    def test_student_group_str(self):
        """Тест строкового представления группы"""
        self.assertEqual(str(self.group), 'ТЕСТ-21')
    
    def test_student_str(self):
        """Тест строкового представления студента"""
        self.assertEqual(str(self.student), 'Студент 123')
    
    def test_discipline_str(self):
        """Тест строкового представления дисциплины"""
        self.assertEqual(str(self.discipline), 'Тестовая дисциплина')
    
    def test_result_type_str(self):
        """Тест строкового представления типа результата"""
        self.assertEqual(str(self.result_type), '5')
    
    def test_student_result_creation(self):
        """Тест создания результата студента"""
        student_result = StudentResult.objects.create(
            student=self.student,
            discipline=self.discipline,
            result=self.result_type
        )
        
        self.assertIsNotNone(student_result)
        self.assertEqual(student_result.student, self.student)
        self.assertEqual(student_result.discipline, self.discipline)
        self.assertEqual(student_result.result, self.result_type)


# ============================================================
# ЗАПУСК ТЕСТОВ
# ============================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])