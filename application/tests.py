import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock, Mock
from django.http import HttpRequest
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from application.api import GradesViewset, AcademicPerformanceViewSet, SubjectStatisticsViewSet, StudentRatingViewSet


class TestGradesViewsetWithMocks:
    """Тесты для GradesViewset"""
    
    @pytest.fixture
    def viewset(self):
        return GradesViewset()
    
    @pytest.fixture
    def mock_request(self):
        factory = APIRequestFactory()
        return factory.get('/api/grades/')
    
    def test_normalize_grade(self, viewset):
        """Тестирование нормализации оценок"""
        test_cases = [
            ("5", "5"),
            ("4", "4"),
            ("3", "3"),
            ("2", "2"),
            ("Зачтено", "зачет"),
            ("Не зачтено", "незачет"),
            ("Н/Я", "неявка"),
            ("", "Не указано"),
            ("Неизвестно", "Неизвестно")
        ]
        
        for input_grade, expected_output in test_cases:
            result = viewset.normalize_grade(input_grade)
            assert result == expected_output, f"Failed for input: {input_grade}"
    
    def test_extract_year_from_group_name(self, viewset):
        """Тестирование извлечения года из названия группы"""
        test_cases = [
            ("ФИТ-21Б", 2021),
            ("МАТ-19А", 2019),
            ("ФИЗ-23", 2023),
            ("ИВТ-20В", 2020),
            ("Некорректное-название", None),
            ("Без-дефиса", None),
            ("", None),
            (None, None)
        ]
        
        for group_name, expected_year in test_cases:
            result = viewset.extract_year_from_group_name(group_name)
            assert result == expected_year, f"Failed for group: {group_name}"
    
    @patch('application.api.datetime')
    def test_calculate_course(self, mock_datetime, viewset):
        """Тестирование расчета курса"""
        # Январь 2024 - до сентября
        mock_datetime.now.return_value = datetime(2024, 1, 15)
        assert viewset.calculate_course(2021) == 3
        
        # Сентябрь 2024 - после сентября
        mock_datetime.now.return_value = datetime(2024, 9, 15)
        assert viewset.calculate_course(2021) == 4
        
        # Декабрь 2024 - после сентября
        mock_datetime.now.return_value = datetime(2024, 12, 15)
        assert viewset.calculate_course(2021) == 4
    
    def test_student_is_still_enrolled(self, viewset):
        """Тестирование проверки, учится ли студент"""
        # Текущий год меньше года выпуска
        with patch('application.api.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 6, 1)
            assert viewset.student_is_still_enrolled(2021) == True
        
        # Текущий год равен году выпуска, но месяц до июля
        with patch('application.api.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 6, 1)
            assert viewset.student_is_still_enrolled(2021) == True
        
        # Текущий год равен году выпуска, месяц после июля
        with patch('application.api.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 8, 1)
            assert viewset.student_is_still_enrolled(2021) == False
        
        # Текущий год больше года выпуска
        with patch('application.api.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 1, 1)
            assert viewset.student_is_still_enrolled(2021) == False
    
    def test_update_grade_stats(self, viewset):
        """Тестирование обновления статистики оценок"""
        grade_stats = {
            'numeric_grades': [],
            'countGrade2': 0, 'countGrade3': 0, 'countGrade4': 0, 'countGrade5': 0,
            'countZachet': 0, 'countNejavka': 0, 'countNezachet': 0
        }
        
        # Тестируем числовые оценки
        viewset.update_grade_stats(grade_stats, "5")
        assert grade_stats['countGrade5'] == 1
        assert grade_stats['numeric_grades'] == [5]
        
        viewset.update_grade_stats(grade_stats, "4")
        assert grade_stats['countGrade4'] == 1
        assert grade_stats['numeric_grades'] == [5, 4]
        
        # Тестируем зачеты/незачеты
        viewset.update_grade_stats(grade_stats, "зачет")
        assert grade_stats['countZachet'] == 1
        
        viewset.update_grade_stats(grade_stats, "незачет")
        assert grade_stats['countNezachet'] == 1
        
        # Тестируем неявку
        viewset.update_grade_stats(grade_stats, "неявка")
        assert grade_stats['countNejavka'] == 1
    
    @patch('application.api.StudentResult.objects')
    def test_list_method_with_mocks(self, mock_studentresult, viewset, mock_request):
        """Тестирование метода list"""
        # Создаем моки для объектов
        mock_student1 = MagicMock()
        mock_student1.student_id = 1
        mock_student1.group.name = "ФИТ-21Б"
        mock_student1.is_academic = False
        
        mock_student2 = MagicMock()
        mock_student2.student_id = 2
        mock_student2.group.name = "ФИТ-21Б"
        mock_student2.is_academic = False
        
        mock_discipline1 = MagicMock()
        mock_discipline1.name = "Математика"
        mock_discipline1.discipline_id = 1
        
        mock_discipline2 = MagicMock()
        mock_discipline2.name = "Физика"
        mock_discipline2.discipline_id = 2
        
        mock_result1 = MagicMock()
        mock_result1.result_value = "5"
        
        mock_result2 = MagicMock()
        mock_result2.result_value = "4"
        
        # Мокаем queryset
        mock_queryset = MagicMock()
        mock_queryset.select_related.return_value.filter.return_value = [
            MagicMock(
                student=mock_student1,
                discipline=mock_discipline1,
                result=mock_result1
            ),
            MagicMock(
                student=mock_student1,
                discipline=mock_discipline2,
                result=mock_result2
            ),
            MagicMock(
                student=mock_student2,
                discipline=mock_discipline1,
                result=mock_result1
            )
        ]
        
        mock_studentresult.select_related.return_value.filter.return_value = mock_queryset
        
        # Мокаем request
        viewset.request = mock_request
        viewset.request.query_params = {}
        
        # Вызываем метод list
        response = viewset.list(mock_request)
        
        # Проверяем, что метод выполнился без ошибок
        assert response.status_code == 200
        assert 'summary' in response.data
        assert 'students' in response.data
        assert 'subjects' in response.data
    
    @patch('application.api.StudentResult.objects')
    def test_list_with_filters(self, mock_studentresult, viewset, mock_request):
        """Тестирование метода list с фильтрами"""
        # Настраиваем моки
        mock_student = MagicMock()
        mock_student.student_id = 1
        mock_student.group.name = "ФИТ-21Б"
        mock_student.is_academic = False
        
        mock_discipline = MagicMock()
        mock_discipline.name = "Математика"
        mock_discipline.discipline_id = 1
        
        mock_result = MagicMock()
        mock_result.result_value = "5"
        
        mock_queryset = MagicMock()
        mock_queryset.select_related.return_value.filter.return_value = [
            MagicMock(
                student=mock_student,
                discipline=mock_discipline,
                result=mock_result
            )
        ]
        
        mock_studentresult.select_related.return_value.filter.return_value = mock_queryset
        
        # Тестируем с фильтром по группе
        mock_request.query_params = {'group': 'ФИТ-21Б'}
        viewset.request = mock_request
        
        response = viewset.list(mock_request)
        assert response.status_code == 200


class TestAcademicPerformanceViewSetWithMocks:
    """Тесты для AcademicPerformanceViewSet"""
    
    @pytest.fixture
    def viewset(self):
        return AcademicPerformanceViewSet()
    
    @pytest.fixture
    def mock_request(self):
        factory = APIRequestFactory()
        return factory.get('/api/academic-performance/')
    
    def test_get_debts_filter(self, viewset):
        """Тестирование фильтра задолженностей"""
        debts_filter = viewset.get_debts_filter()
        
        # Проверяем, что фильтр содержит правильные условия
        assert debts_filter is not None
        
        # Можно проверить строковое представление фильтра
        filter_str = str(debts_filter)
        assert '2' in filter_str or 'Н/Я' in filter_str or 'Не зачтено' in filter_str
    
    @patch('application.api.Student.objects')
    def test_get_queryset(self, mock_student, viewset):
        """Тестирование базового queryset"""
        # Мокаем аннотированный queryset
        mock_queryset = MagicMock()
        mock_student.select_related.return_value.filter.return_value.annotate.return_value.order_by.return_value = mock_queryset
        
        queryset = viewset.get_queryset()
        
        # Проверяем, что методы были вызваны с правильными параметрами
        mock_student.select_related.assert_called_once_with('group')
        mock_student.select_related.return_value.filter.assert_called_once()
    
    @patch('application.api.Student.objects')
    @patch('application.api.StudentGroup.objects')
    def test_calculate_group_stats(self, mock_studentgroup, mock_student, viewset):
        """Тестирование расчета статистики по группам"""
        # Мокаем группы
        mock_group1 = MagicMock()
        mock_group1.name = "ФИТ-21Б"
        
        mock_group2 = MagicMock()
        mock_group2.name = "ФИТ-22А"
        
        mock_studentgroup.filter.return_value = [mock_group1, mock_group2]
        
        # Мокаем студентов с задолженностями
        mock_student1 = MagicMock()
        mock_student1.debt_count = 2
        
        mock_student2 = MagicMock()
        mock_student2.debt_count = 0
        
        mock_student3 = MagicMock()
        mock_student3.debt_count = 1
        
        # Мокаем queryset для фильтрации по группам
        mock_queryset = MagicMock()
        mock_queryset.filter.return_value.exists.return_value = True
        mock_queryset.filter.return_value.__iter__ = Mock(return_value=iter([mock_student1, mock_student2]))
        mock_queryset.filter.return_value.__len__ = Mock(return_value=2)
        
        mock_student.select_related.return_value.filter.return_value.annotate.return_value.order_by.return_value = mock_queryset
        
        group_stats = viewset.calculate_group_stats(mock_queryset)
        
        # Проверяем структуру ответа
        assert isinstance(group_stats, list)
        assert len(group_stats) == 2
        for stat in group_stats:
            assert 'group' in stat
            assert 'avgDebts' in stat
            assert isinstance(stat['avgDebts'], float)
    
    def test_get_debt_distribution(self, viewset):
        """Тестирование распределения задолженностей"""
        # Создаем мок студентов с разным количеством задолженностей
        mock_students = [
            MagicMock(debt_count=0),  # 0 долгов
            MagicMock(debt_count=0),  # 0 долгов
            MagicMock(debt_count=1),  # 1 долг
            MagicMock(debt_count=2),  # 2 долга
            MagicMock(debt_count=2),  # 2 долга
            MagicMock(debt_count=3),  # 3+ долга
            MagicMock(debt_count=5),  # 3+ долга
        ]
        
        distribution = viewset.get_debt_distribution(mock_students)
        
        assert distribution['zero_debts'] == 2
        assert distribution['one_debt'] == 1
        assert distribution['two_debts'] == 2
        assert distribution['three_plus_debts'] == 2
    
    @patch('application.api.StudentResult.objects')
    def test_get_student_debts_details(self, mock_studentresult, viewset):
        """Тестирование получения деталей задолженностей"""
        # Мокаем студента
        mock_student = MagicMock()
        mock_student.student_id = 1
        
        # Мокаем долги
        mock_debt1 = MagicMock()
        mock_debt1.discipline.name = "Математика"
        mock_debt1.result.result_value = "2"
        
        mock_debt2 = MagicMock()
        mock_debt2.discipline.name = "Физика"
        mock_debt2.result.result_value = "Н/Я"
        
        mock_studentresult.filter.return_value.select_related.return_value = [mock_debt1, mock_debt2]
        
        debts_details = viewset.get_student_debts_details(mock_student)
        
        assert len(debts_details) == 2
        assert debts_details[0]['discipline'] == "Математика"
        assert debts_details[0]['grade'] == "2"
        assert debts_details[1]['discipline'] == "Физика"
        assert debts_details[1]['grade'] == "Н/Я"


class TestSubjectStatisticsViewSetWithMocks:
    """Тесты для SubjectStatisticsViewSet"""
    
    @pytest.fixture
    def viewset(self):
        return SubjectStatisticsViewSet()
    
    @pytest.fixture
    def mock_request(self):
        factory = APIRequestFactory()
        return factory.get('/api/subject-statistics/')
    
    def test_normalize_grade_value(self, viewset):
        """Тестирование нормализации значений оценок"""
        test_cases = [
            ("5", 5),
            ("4", 4),
            ("3", 3),
            ("2", 2),
            ("Зачтено", "зачет"),
            ("Не зачтено", "незачет"),
            ("Н/Я", "неявка"),
            ("", None),
            ("Неизвестно", None),
            ("6", None),
            ("1", None)
        ]
        
        for input_value, expected_output in test_cases:
            result = viewset.normalize_grade_value(input_value)
            assert result == expected_output, f"Failed for input: {input_value}"
    
    @patch('application.api.StudentResult.objects')
    @patch('application.api.Attendance.objects')
    @patch('application.api.Student.objects')
    def test_list_method_with_mocks(self, mock_student, mock_attendance, mock_studentresult, viewset, mock_request):
        """Тестирование метода list с моками"""
        # Мокаем студентов
        mock_student1 = MagicMock()
        mock_student1.student_id = 1
        mock_student1.group.name = "ФИТ-21Б"
        
        mock_student.objects.select_related.return_value.filter.return_value = [mock_student1]
        
        # Мокаем результаты
        mock_discipline1 = MagicMock()
        mock_discipline1.discipline_id = 1
        mock_discipline1.name = "Математика"
        
        mock_discipline2 = MagicMock()
        mock_discipline2.discipline_id = 2
        mock_discipline2.name = "Физика"
        
        mock_result1 = MagicMock()
        mock_result1.result.result_value = "5"
        
        mock_result2 = MagicMock()
        mock_result2.result.result_value = "4"
        
        mock_queryset = MagicMock()
        mock_queryset.select_related.return_value.filter.return_value = [
            MagicMock(
                student=mock_student1,
                discipline=mock_discipline1,
                result=mock_result1.result
            ),
            MagicMock(
                student=mock_student1,
                discipline=mock_discipline2,
                result=mock_result2.result
            )
        ]
        
        mock_studentresult.select_related.return_value.filter.return_value = mock_queryset
        
        # Мокаем посещаемость
        mock_attendance_stats = MagicMock()
        mock_attendance_stats.aggregate.return_value = {
            'unique_lessons': 10,
            'unique_students': 5
        }
        mock_attendance.filter.return_value = mock_attendance_stats
        
        # Настраиваем request
        viewset.request = mock_request
        viewset.request.query_params = {}
        
        # Вызываем метод list
        response = viewset.list(mock_request)
        
        # Проверяем структуру ответа
        assert response.status_code == 200
        assert 'subjectStats' in response.data
        assert 'gradeDistributionBar' in response.data
        assert 'bestSubjects' in response.data


class TestStudentRatingViewSetWithMocks:
    """Тесты для StudentRatingViewSet"""
    
    @pytest.fixture
    def viewset(self):
        return StudentRatingViewSet()
    
    @pytest.fixture
    def mock_request(self):
        factory = APIRequestFactory()
        return factory.get('/api/student-rating/')
    
    def test_normalize_grade_value(self, viewset):
        """Тестирование нормализации значений оценок"""
        test_cases = [
            ("5", 5),
            ("4", 4),
            ("3", 3),
            ("2", 2),
            ("Зачтено", None),  # В этом ViewSet только числовые оценки
            ("Не зачтено", None),
            ("Н/Я", None),
            ("", None),
            ("6", None),
            ("1", None)
        ]
        
        for input_value, expected_output in test_cases:
            result = viewset.normalize_grade_value(input_value)
            assert result == expected_output, f"Failed for input: {input_value}"
    
    def test_classify_debt_type(self, viewset):
        """Тестирование классификации типов долгов"""
        test_cases = [
            ("2", "неуд"),
            ("Н/Я", "неявка"),
            ("Не зачтено", "незачет"),
            ("Другое", "другой"),
            ("", "другой"),
            (None, "другой")
        ]
        
        for grade_value, expected_type in test_cases:
            result = viewset.classify_debt_type(grade_value)
            assert result == expected_type, f"Failed for grade: {grade_value}"
    
    @pytest.mark.parametrize("risk_score,expected_level", [
        (0.0, "низкий"),
        (0.1, "низкий"),
        (0.29, "низкий"),
        (0.3, "средний"),
        (0.5, "средний"),
        (0.69, "средний"),
        (0.7, "высокий"),
        (0.9, "высокий"),
        (1.0, "высокий")
    ])
    def test_get_risk_level(self, risk_score, expected_level, viewset):
        """Тестирование определения уровня риска"""
        result = viewset.get_risk_level(risk_score)
        assert result == expected_level
    
    @patch('application.api.StudentResult.objects')
    def test_calculate_student_activity(self, mock_studentresult, viewset):
        """Тестирование расчета активности студента"""
        # Мокаем результаты студента
        mock_passed_subjects = MagicMock()
        mock_passed_subjects.count.return_value = 8
        
        mock_studentresult.filter.return_value = mock_passed_subjects
        
        # Мокаем посещаемость
        with patch('application.api.Attendance.objects') as mock_attendance:
            mock_attendance_count = MagicMock()
            mock_attendance_count.count.return_value = 45
            mock_attendance.filter.return_value = mock_attendance_count
            
            activity = viewset.calculate_student_activity(1)
            
            # Проверяем, что активность в пределах 0-5
            assert 0 <= activity <= 5.0
            assert isinstance(activity, float)
    
    @patch('application.api.Attendance.objects')
    def test_calculate_attendance_percent(self, mock_attendance, viewset):
        """Тестирование расчета процента посещаемости"""
        # Мокаем количество посещений
        mock_attendance_count = MagicMock()
        mock_attendance_count.count.return_value = 45
        mock_attendance.filter.return_value = mock_attendance_count
        
        attendance_percent = viewset.calculate_attendance_percent(1)
        
        # Проверяем, что процент в пределах 0-100
        assert 0 <= attendance_percent <= 100.0
        assert isinstance(attendance_percent, float)
        
        # Тест с нулевыми посещениями
        mock_attendance_count.count.return_value = 0
        attendance_percent = viewset.calculate_attendance_percent(1)
        assert attendance_percent == 0.0
    
    @patch('application.api.StudentResult.objects')
    def test_calculate_dropout_risk(self, mock_studentresult, viewset):
        """Тестирование расчета риска отчисления"""
        # Мокаем количество долгов
        mock_debts = MagicMock()
        mock_debts.count.return_value = 2
        mock_studentresult.filter.return_value = mock_debts
        
        risk = viewset.calculate_dropout_risk(
            student_id=1,
            avg_grade=3.5,
            attendance_percent=75.0,
            activity=3.0
        )
        
        # Проверяем, что риск в пределах 0-1
        assert 0 <= risk <= 1.0
        assert isinstance(risk, float)
    
    @patch('application.api.StudentResult.objects')
    def test_get_student_debts_details(self, mock_studentresult, viewset):
        """Тестирование получения деталей задолженностей"""
        # Мокаем долги
        mock_discipline1 = MagicMock()
        mock_discipline1.name = "Математика"
        
        mock_discipline2 = MagicMock()
        mock_discipline2.name = "Физика"
        
        mock_result1 = MagicMock()
        mock_result1.result_value = "2"
        
        mock_result2 = MagicMock()
        mock_result2.result_value = "Н/Я"
        
        mock_debt1 = MagicMock()
        mock_debt1.discipline = mock_discipline1
        mock_debt1.result = mock_result1
        
        mock_debt2 = MagicMock()
        mock_debt2.discipline = mock_discipline2
        mock_debt2.result = mock_result2
        
        mock_studentresult.filter.return_value.select_related.return_value = [mock_debt1, mock_debt2]
        
        debts_details = viewset.get_student_debts_details(1)
        
        assert len(debts_details) == 2
        assert debts_details[0]['discipline'] == "Математика"
        assert debts_details[0]['grade'] == "2"
        assert debts_details[0]['type'] == "неуд"
        assert debts_details[1]['discipline'] == "Физика"
        assert debts_details[1]['grade'] == "Н/Я"
        assert debts_details[1]['type'] == "неявка"


class TestEdgeCasesWithMocks:
    """Тесты для граничных случаев с моками"""
    
    def test_empty_inputs_grades_viewset(self):
        """Тестирование обработки пустых входных данных в GradesViewset"""
        viewset = GradesViewset()
        
        # Пустые строки и None
        assert viewset.normalize_grade("") == "Не указано"
        assert viewset.normalize_grade(None) == "Не указано"
        
        # Некорректные названия групп
        assert viewset.extract_year_from_group_name("") is None
        assert viewset.extract_year_from_group_name("Некорректно") is None
        assert viewset.extract_year_from_group_name("ФИТ") is None
        assert viewset.extract_year_from_group_name("ФИТ-") is None
    
    def test_invalid_grade_values_all_viewsets(self):
        """Тестирование обработки невалидных оценок во всех ViewSet"""
        grades_viewset = GradesViewset()
        subject_viewset = SubjectStatisticsViewSet()
        rating_viewset = StudentRatingViewSet()
        
        # Невалидные числовые значения
        invalid_grades = ["6", "1", "0", "-1", "1.5", "abc", "!"]
        
        for invalid_grade in invalid_grades:
            # GradesViewset оставляет как есть
            assert grades_viewset.normalize_grade(invalid_grade) == invalid_grade
            
            # SubjectStatisticsViewSet возвращает None
            assert subject_viewset.normalize_grade_value(invalid_grade) is None
            
            # StudentRatingViewSet возвращает None
            assert rating_viewset.normalize_grade_value(invalid_grade) is None
    
    @patch('application.api.datetime')
    def test_boundary_dates_course_calculation(self, mock_datetime, viewset=None):
        """Тестирование граничных дат для расчета курса"""
        if viewset is None:
            viewset = GradesViewset()
        
        # 31 августа - еще старый курс
        mock_datetime.now.return_value = datetime(2024, 8, 31)
        assert viewset.calculate_course(2021) == 3
        
        # 1 сентября - уже новый курс
        mock_datetime.now.return_value = datetime(2024, 9, 1)
        assert viewset.calculate_course(2021) == 4
        
        # 31 декабря - все еще новый курс
        mock_datetime.now.return_value = datetime(2024, 12, 31)
        assert viewset.calculate_course(2021) == 4


# Интеграционные тесты с моками
class TestIntegrationWithMocks:
    """Интеграционные тесты с полным мокированием"""
    
    @patch('application.api.Student.objects')
    @patch('application.api.StudentResult.objects')
    @patch('application.api.Attendance.objects')
    def test_complete_student_rating_flow(self, mock_attendance, mock_studentresult, mock_student):
        """Тест полного потока расчета рейтинга студента"""
        viewset = StudentRatingViewSet()
        
        # Мокаем студентов
        mock_student1 = MagicMock()
        mock_student1.student_id = 1
        mock_student1.group.name = "ФИТ-21Б"
        mock_student1.group.speciality.faculty.name = "ФИТ"
        
        mock_student.objects.select_related.return_value.filter.return_value = [mock_student1]
        
        # Мокаем результаты с оценками
        mock_result_queryset = MagicMock()
        mock_result_queryset.select_related.return_value = [
            MagicMock(result=MagicMock(result_value="5")),
            MagicMock(result=MagicMock(result_value="4")),
            MagicMock(result=MagicMock(result_value="5"))
        ]
        mock_studentresult.filter.return_value = mock_result_queryset
        
        # Мокаем посещаемость
        mock_attendance.filter.return_value.count.return_value = 50
        
        # Мокаем долги
        mock_debts = MagicMock()
        mock_debts.count.return_value = 1
        mock_studentresult.filter.return_value = mock_debts
        
        # Тестируем расчет среднего балла
        numeric_grades = []
        for result in mock_result_queryset.select_related.return_value:
            grade_value = viewset.normalize_grade_value(result.result.result_value)
            if grade_value and 2 <= grade_value <= 5:
                numeric_grades.append(grade_value)
        
        assert numeric_grades == [5, 4, 5]
        assert sum(numeric_grades) / len(numeric_grades) == pytest.approx(4.67, 0.01)
        
        # Тестируем расчет активности
        mock_passed_subjects = MagicMock()
        mock_passed_subjects.count.return_value = 10
        mock_studentresult.filter.return_value = mock_passed_subjects
        
        activity = viewset.calculate_student_activity(1)
        assert 0 <= activity <= 5.0
        
        # Тестируем расчет посещаемости
        attendance_percent = viewset.calculate_attendance_percent(1)
        assert 0 <= attendance_percent <= 100.0
        
        # Тестируем расчет риска
        risk = viewset.calculate_dropout_risk(1, 4.67, attendance_percent, activity)
        assert 0 <= risk <= 1.0


if __name__ == "__main__":
    print("Running mocked tests...")
    
    # Test GradesViewset
    test_grades = TestGradesViewsetWithMocks()
    test_grades.test_normalize_grade()
    test_grades.test_extract_year_from_group_name()
    test_grades.test_update_grade_stats()
    
    # Test StudentRatingViewSet
    test_rating = TestStudentRatingViewSetWithMocks()
    test_rating.test_normalize_grade_value()
    test_rating.test_classify_debt_type()
    test_rating.test_get_risk_level(0.1, "низкий")