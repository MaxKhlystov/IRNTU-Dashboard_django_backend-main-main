from collections import defaultdict
from datetime import datetime
from typing import Optional, List, Dict, Any
from django.db.models import Count
from application.models import Student, StudentResult, Discipline, Attendance

class SubjectStatisticsService:
    """
    Сервис для анализа успеваемости по учебным дисциплинам.
    
    Предоставляет методы для:
    - Определения курса обучения студентов.
    - Нормализации оценок из строкового формата в числовой/категориальный.
    - Расчета относительной посещаемости по предметам.
    - Вычисления интегрального показателя "Активность предмета".
    - Формирования сводной статистики и рейтинга дисциплин.
    
    Основная цель: выявить наиболее успешные и проблемные предметы на основе 
    комплексного анализа оценок, посещаемости и количества задолженностей.
    """
    @staticmethod
    def calculate_course(year_of_admission: int) -> int:
        """
        Вычисляет текущий курс студента на основе года поступления.
        
        Логика:
        - Учебный год начинается 1 сентября.
        - Если текущий месяц < 9, курс = текущий год - год поступления.
        - Если текущий месяц >= 9, курс увеличивается на 1.
        
        Args:
            year_of_admission (int): Год поступления (например, 2023).
            
        Returns:
            int: Номер текущего курса (1, 2, 3, ...).
        """
        now = datetime.now()
        current_year = now.year
        current_month = now.month
        if current_month < 9:
            return current_year - year_of_admission
        else:
            return current_year - year_of_admission + 1

    @staticmethod
    def extract_year_from_group_name(name: str) -> Optional[int]:
        """
        Извлекает год поступления из названия учебной группы.
        
        Ожидает формат "Название-ГГ" (например, "КСм-23").
        Автоматически определяет век (19xx или 20xx) относительно текущего года.
        
        Args:
            name (str): Название группы.
            
        Returns:
            Optional[int]: Полный год поступления или None при ошибке формата.
        """
        try:
            parts = name.split('-')
            if len(parts) < 2:
                return None
            year_part = parts[1][:2]
            year_suffix = int(year_part)
            current_year = datetime.now().year % 100
            century = 2000 if year_suffix <= current_year else 1900
            return century + year_suffix
        except (IndexError, ValueError, AttributeError):
            return None

    @staticmethod
    def normalize_grade_value(result_value: str):
        """
        Нормализует строковое значение оценки в стандартный формат.
        
        Преобразования:
        - "2", "3", "4", "5" -> int (2, 3, 4, 5)
        - "Зачтено" -> "зачет"
        - "Не зачтено" -> "незачет"
        - "Н/Я" -> "неявка"
        - Пустые значения -> None
        - Прочее -> None
        
        Args:
            result_value (str): Исходное значение оценки.
            
        Returns:
            Union[int, str, None]: Нормализованное значение или None.
        """
        if not result_value:
            return None
        grade_clean = result_value.strip()
        if grade_clean in ["2", "3", "4", "5"]:
            return int(grade_clean)
        elif grade_clean == "Зачтено":
            return "зачет"
        elif grade_clean == "Не зачтено":
            return "незачет"
        elif grade_clean == "Н/Я":
            return "неявка"
        return None

    @classmethod
    def get_students_in_course(cls, course: int) -> List[int]:
        """
        Возвращает список ID студентов, обучающихся на указанном курсе.
        
        Фильтрует студентов, не находящихся в академическом отпуске,
        и вычисляет их курс на основе названия группы.
        
        Args:
            course (int): Номер курса для фильтрации.
            
        Returns:
            List[int]: Список идентификаторов студентов (student_id).
        """
        student_ids = []
        students = Student.objects.select_related('group').filter(is_academic=False)
        for student in students:
            if student.group and student.group.name:
                year = cls.extract_year_from_group_name(student.group.name)
                if year is not None:
                    student_course = cls.calculate_course(year)
                    if student_course == course:
                        student_ids.append(student.student_id)
        return student_ids

    @classmethod
    def get_attendance_percent_for_discipline(cls, discipline_id: int, student_ids: List[int]) -> float:
        """
        Рассчитывает средний процент посещаемости по группе студентов для конкретного предмета.
        
        Логика расчета (относительная метрика):
        1. Для каждого студента считается количество посещений данного предмета.
        2. Находится максимальное количество посещений среди всех студентов выборки (эталон).
        3. Для каждого студента вычисляется процент: (посещения / максимум) * 100.
        4. Возвращается среднее арифметическое этих процентов.
        
        Это позволяет оценить вовлеченность группы в предмет без знания общего количества пар.
        
        Args:
            discipline_id (int): ID дисциплины.
            student_ids (List[int]): Список ID студентов для анализа.
            
        Returns:
            float: Средний процент посещаемости (0.0 - 100.0).
        """
        if not student_ids:
            return 0.0

        # 1. Считаем количество посещений для КАЖДОГО студента по этому предмету
        attendance_stats = Attendance.objects.filter(
            discipline_id=discipline_id,
            student_id__in=student_ids
        ).values('student_id').annotate(
            visits=Count('lesson_id')
        )

        if not attendance_stats:
            return 0.0

        stats_list = list(attendance_stats)
        visits_counts = [item['visits'] for item in stats_list]
        
        # 2. Находим максимальное количество посещений среди этих студентов (эталон)
        max_visits = max(visits_counts) if visits_counts else 0
        
        if max_visits == 0:
            return 0.0

        # 3. Считаем процент для каждого студента и усредняем их 
        total_percentage = 0.0
        for visits in visits_counts:
            percent = (visits / max_visits) * 100
            total_percentage += percent
        
        avg_percentage = total_percentage / len(visits_counts)
        
        return round(avg_percentage, 2)

    @classmethod
    def calculate_activity_for_discipline(cls, avg_grade: float, attendance_percent: float, debt_ratio: float) -> float:
        """
        Рассчитывает интегральный показатель активности по предмету (шкала 0.0 - 5.0).
        
        Формула расчета:
        Activity = (GradeScore * 0.5) + (AttendanceScore * 0.3) + (DebtFreeBonus * 0.2)
        
        Где:
        - GradeScore: Средний балл (0-5). Вес 50%.
        - AttendanceScore: Посещаемость, нормированная к шкале 0-5. Вес 30%.
        - DebtFreeBonus: Бонус за отсутствие долгов (5.0 * (1 - доля_долгов)). Вес 20%.
        
        Args:
            avg_grade (float): Средний балл по предмету (0-5).
            attendance_percent (float): Средняя посещаемость в процентах (0-100).
            debt_ratio (float): Доля студентов с долгами (0.0 - 1.0).
            
        Returns:
            float: Показатель активности (0.0 - 5.0).
        """
        # 1. Компонент успеваемости (шкала 0-5)
        grade_score = avg_grade 

        # 2. Компонент посещаемости (переводим 0-100% в шкалу 0-5)
        attendance_score = (attendance_percent / 100.0) * 5.0

        # 3. Компонент долгов (чем меньше долгов, тем выше балл)
        # Если долгов нет (0.0) -> добавляем 1.0 (макс бонус)
        # Если все имеют долги (1.0) -> добавляем 0.0
        # Вес этого компонента в итоговой формуле будет учтен множителем
        debt_free_bonus = (1.0 - debt_ratio) * 5.0 

        # Итоговая взвешенная сумма
        # 50% успеваемость + 30% посещаемость + 20% отсутствие долгов
        activity = (grade_score * 0.5) + (attendance_score * 0.3) + (debt_free_bonus * 0.2)
        
        return round(min(activity, 5.0), 2)

    @classmethod
    def get_statistics(
        cls,
        course: Optional[int] = None,
        subject: Optional[str] = None,
        groups: Optional[List[str]] = None,
        sort_by: str = 'avg',
        limit: int = 5
    ) -> Dict[str, Any]:
        """
        Основной метод сервиса. Собирает полную статистику по предметам с фильтрацией.
        
        Выполняет следующие шаги:
        1. Формирует выборку результатов успеваемости (StudentResult) с учетом фильтров.
        2. Агрегирует данные по дисциплинам: оценки, количество студентов, количество долгов.
        3. Рассчитывает общую статистику (средний балл, мин/макс, распределение оценок).
        4. Для каждого предмета вычисляет посещаемость и интегральную активность.
        5. Формирует рейтинг предметов (топ-N) с возможностью сортировки по разным метрикам.
        
        Args:
            course (int, optional): Фильтр по номеру курса.
            subject (str, optional): Фильтр по названию предмета (поиск по подстроке).
            groups (List[str], optional): Фильтр по списку названий групп.
            sort_by (str): Критерий сортировки ('avg', 'max', 'count', 'activity').
            limit (int): Количество возвращаемых лучших предметов.
            
        Returns:
            Dict[str, Any]: Структурированные данные:
                {
                    "subjectStats": {
                        "minGrade": float|null,
                        "avgGrade": float|null,
                        "maxGrade": float|null
                    },
                    "gradeDistributionBar": {
                        "2": int, "3": int, "4": int, "5": int
                    },
                    "bestSubjects": [
                        {
                            "subject": str,
                            "avg": float,
                            "max": int,
                            "count": int,
                            "avgAttendance": float,
                            "avgActivity": float
                        },
                        ...
                    ]
                }
        """
        results_qs = StudentResult.objects.select_related(
            'student__group', 'discipline', 'result'
        ).filter(student__is_academic=False)

        # Фильтр по группам
        if groups:
            results_qs = results_qs.filter(student__group__name__in=groups)

        # Фильтр по курсу
        if course is not None:
            student_ids = cls.get_students_in_course(course)
            if not student_ids:
                return cls._empty_response()
            results_qs = results_qs.filter(student_id__in=student_ids)

        # Фильтр по предмету
        if subject:
            results_qs = results_qs.filter(discipline__name__icontains=subject)

        # Сбор данных
        numeric_grades = []
        grade_distribution_bar = {'2': 0, '3': 0, '4': 0, '5': 0}
        
        # Структура для хранения детальных данных по предметам
        subject_data = defaultdict(lambda: {
            'grades': [],
            'name': None,
            'student_ids': set(),
            'debt_count': 0,
            'total_students_with_result': 0
        })

        for result in results_qs:
            discipline = result.discipline
            result_value = result.result.result_value if result.result else None
            normalized = cls.normalize_grade_value(result_value)
            
            if normalized is None:
                continue

            disc_id = discipline.discipline_id
            subject_data[disc_id]['name'] = discipline.name
            subject_data[disc_id]['student_ids'].add(result.student.student_id)
            subject_data[disc_id]['total_students_with_result'] += 1

            # Обработка числовых оценок и долгов
            if isinstance(normalized, int):
                if 2 <= normalized <= 5:
                    numeric_grades.append(normalized)
                    grade_distribution_bar[str(normalized)] += 1
                    subject_data[disc_id]['grades'].append(normalized)
                    
                    if normalized == 2:
                        subject_data[disc_id]['debt_count'] += 1
            
            # Обработка текстовых долгов ("незачет", "неявка")
            elif normalized in ["незачет", "неявка"]:
                subject_data[disc_id]['debt_count'] += 1

        # Общая статистика
        if numeric_grades:
            subject_stats = {
                "minGrade": min(numeric_grades),
                "avgGrade": round(sum(numeric_grades) / len(numeric_grades), 2),
                "maxGrade": max(numeric_grades)
            }
        else:
            subject_stats = {"minGrade": None, "avgGrade": None, "maxGrade": None}

        # Топ предметов с расчетом активности
        best_subjects_data = []
        for disc_id, data in subject_data.items():
            grades = data['grades']
            total_results = data['total_students_with_result']
            debt_count = data['debt_count']
            
            if not grades and total_results == 0:
                continue
                
            # Расчет среднего балла (только по числовым оценкам)
            avg_grade = sum(grades) / len(grades) if grades else 0.0
            
            # Расчет посещаемости
            avg_attendance = cls.get_attendance_percent_for_discipline(
                disc_id, list(data['student_ids'])
            )
            
            # Расчет доли долгов (относительно всех выставленных результатов)
            debt_ratio = (debt_count / total_results) if total_results > 0 else 0.0
            
            # Расчет активности по новой формуле
            avg_activity = cls.calculate_activity_for_discipline(
                avg_grade=avg_grade,
                attendance_percent=avg_attendance,
                debt_ratio=debt_ratio
            )

            best_subjects_data.append({
                'name': data['name'],
                'avg': round(avg_grade, 2),
                'max': max(grades) if grades else 0,
                'count': len(grades),
                'avg_attendance': avg_attendance,
                'avg_activity': avg_activity
            })

        # Сортировка
        sort_field_map = {
            'avg': 'avg', 
            'max': 'max', 
            'count': 'count',
            'activity': 'avg_activity' 
        }
        sort_field = sort_field_map.get(sort_by, 'avg')
        
        best_subjects_data.sort(key=lambda x: x[sort_field], reverse=True)
        top_subjects = best_subjects_data[:limit]

        best_subjects_response = [
            {
                "subject": s['name'],
                "avg": s['avg'],
                "max": s['max'],
                "count": s['count'],
                "avgAttendance": s['avg_attendance'],
                "avgActivity": s['avg_activity']  
            }
            for s in top_subjects
        ]

        return {
            "subjectStats": subject_stats,
            "gradeDistributionBar": grade_distribution_bar,
            "bestSubjects": best_subjects_response
        }

    @staticmethod
    def _empty_response() -> Dict[str, Any]:
        return {
            "subjectStats": {"minGrade": None, "avgGrade": None, "maxGrade": None},
            "gradeDistributionBar": {'2': 0, '3': 0, '4': 0, '5': 0},
            "bestSubjects": []
        }