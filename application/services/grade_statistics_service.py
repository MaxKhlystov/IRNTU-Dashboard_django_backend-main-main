from collections import defaultdict
from typing import Optional, Set, Tuple
from django.db.models import Q
from application.models import Student, StudentResult
from application.utils.student_utils import (
    extract_year_from_group_name,
    calculate_course,
    student_is_still_enrolled
)

class GradeStatisticsService:
    """
    Сервис для сбора и агрегации статистики успеваемости студентов.
    
    Предоставляет методы для:
    - Нормализации строковых значений оценок.
    - Фильтрации студентов по курсу с учетом года поступления и статуса обучения.
    - Агрегации данных об оценках по студентам, предметам и общей выборке.
    - Формирования сводной статистики (средний балл, распределение оценок).
    
    Возвращает структурированные данные, готовые для отображения в дашбордах аналитики.
    """
    @staticmethod
    def normalize_grade(grade_value: str) -> str:
        """
        Нормализует строковое значение оценки к стандартному формату.
        
        Преобразует различные варианты написания оценок в единый набор ключей:
        - "2", "3", "4", "5" -> остаются без изменений.
        - "Зачтено" -> "зачет"
        - "Не зачтено" -> "незачет"
        - "Н/Я" -> "неявка"
        - Пустые значения -> "Не указано"
        - Любые другие значения -> возвращаются как есть.
        
        Args:
            grade_value (str): Исходное строковое значение оценки из БД.
            
        Returns:
            str: Нормализованное значение оценки.
        """
        if not grade_value:
            return "Не указано"
        grade_clean = grade_value.strip()
        if grade_clean in ["2", "3", "4", "5"]:
            return grade_clean
        elif grade_clean == "Зачтено":
            return "зачет"
        elif grade_clean == "Не зачтено":
            return "незачет"
        elif grade_clean == "Н/Я":
            return "неявка"
        return grade_clean

    @staticmethod
    def get_student_ids_by_course(course: int) -> Set[int]:
        """
        Возвращает множество (set) ID студентов, обучающихся на указанном курсе.
        
        Логика определения курса:
        1. Извлекает год поступления из названия группы (например, "КСм-21" -> 2021).
        2. Проверяет, продолжает ли студент обучение (student_is_still_enrolled).
        3. Вычисляет текущий курс на основе года поступления и текущей даты.
        4. Включает студента в выборку, если рассчитанный курс совпадает с запрошенным.
        
        Args:
            course (int): Номер курса (1, 2, 3, ...).
            
        Returns:
            Set[int]: Множество уникальных идентификаторов студентов (student_id).
        """
        student_ids = set()

        students = Student.objects.filter(
            is_academic=False,
            group__isnull=False
        ).select_related('group')
        for student in students:
            group_name = student.group.name
            year = extract_year_from_group_name(group_name)
            if year is None:
                continue
            if not student_is_still_enrolled(year):
                continue
            if calculate_course(year) == course:
                student_ids.add(student.student_id)
        return student_ids

    @classmethod
    def get_statistics(
        cls,
        course: Optional[int] = None,
        group: Optional[str] = None,
        subject: Optional[str] = None
    ) -> dict:
        """
        Основной метод сервиса. Собирает полную статистику успеваемости с фильтрацией.
        
        Выполняет следующие шаги:
        1. Формирует фильтр QuerySet на основе параметров (курс, группа).
        2. Загружает результаты успеваемости (StudentResult) с оптимизированными JOIN'ами.
        3. Итерируется по результатам, нормализуя оценки и группируя данные по студентам и предметам.
        4. Подсчитывает общую статистику (количество оценок каждого типа, средний балл).
        5. Формирует итоговый словарь с тремя секциями: summary, students, subjects.
        
        Args:
            course (int, optional): Фильтр по номеру курса.
            group (str, optional): Фильтр по названию группы.
            subject (str, optional): Фильтр по названию дисциплины.
            
        Returns:
            dict: Структурированные данные:
                {
                    "summary": {
                        "totalStudents": int,
                        "averageGrade": float|null,
                        "minGrade": int|null,
                        "maxGrade": int|null,
                        "countGrade2": int,
                        "countGrade3": int,
                        "countGrade4": int,
                        "countGrade5": int,
                        "countZachet": int,
                        "countNejavka": int,
                        "countNezachet": int
                    },
                    "students": [
                        {
                            "id": int,
                            "group": str,
                            "course": int|null,
                            "subjects": [
                                {"subject": str, "grades": [str, ...]}
                            ]
                        },
                        ...
                    ],
                    "subjects": [
                        {"id": int, "name": str},
                        ...
                    ]
                }
        """
        # Фильтрация студентов по курсу
        student_filter = Q(student__is_academic=False)
        if group:
            student_filter &= Q(student__group__name=group)
        if course is not None:
            valid_student_ids = cls.get_student_ids_by_course(course)
            if not valid_student_ids:
                # Нет студентов на этом курсе
                return {
                    "summary": {
                        "totalStudents": 0,
                        "averageGrade": None,
                        "minGrade": None,
                        "maxGrade": None,
                        "countGrade2": 0,
                        "countGrade3": 0,
                        "countGrade4": 0,
                        "countGrade5": 0,
                        "countZachet": 0,
                        "countNejavka": 0,
                        "countNezachet": 0,
                    },
                    "students": [],
                    "subjects": []
                }
            student_filter &= Q(student_id__in=valid_student_ids)

        results_qs = StudentResult.objects.select_related(
            'student__group',
            'discipline',
            'result'
        ).filter(student_filter)

        if subject:
            results_qs = results_qs.filter(discipline__name=subject)

        # Сбор данных
        students_data_dict = defaultdict(lambda: {
            "id": None,
            "group": None,
            "course": None,
            "subjects": defaultdict(list)
        })
        subjects_info: Set[Tuple[str, int]] = set()
        grade_stats = {
            'numeric_grades': [],
            'countGrade2': 0,
            'countGrade3': 0,
            'countGrade4': 0,
            'countGrade5': 0,
            'countZachet': 0,
            'countNejavka': 0,
            'countNezachet': 0
        }

        for result in results_qs:
            student = result.student
            discipline = result.discipline
            result_value = result.result.result_value if result.result else None

            if not result_value or not discipline:
                continue

            # Определяем курс студента
            course_num = None
            if student.group and student.group.name:
                year = extract_year_from_group_name(student.group.name)
                if year is not None:
                    course_num = calculate_course(year)

            # Заполняем данные
            sid = student.student_id
            students_data_dict[sid]["id"] = sid
            students_data_dict[sid]["group"] = student.group.name if student.group else None
            students_data_dict[sid]["course"] = course_num

            disc_name = discipline.name
            subjects_info.add((disc_name, discipline.discipline_id))
            normalized = cls.normalize_grade(result_value)
            students_data_dict[sid]["subjects"][disc_name].append(normalized)
            cls.update_grade_stats(grade_stats, normalized)

        # Формируем ответ
        students_data = []
        for data in students_data_dict.values():
            if data["id"] is None:
                continue
            subjects_list = [
                {"subject": name, "grades": grades}
                for name, grades in data["subjects"].items()
            ]
            students_data.append({
                "id": data["id"],
                "group": data["group"],
                "course": data["course"],
                "subjects": subjects_list
            })

        numeric_grades = grade_stats['numeric_grades']
        total_students = len(students_data)
        summary = {
            "totalStudents": total_students,
            "averageGrade": round(sum(numeric_grades) / len(numeric_grades), 2) if numeric_grades else None,
            "minGrade": min(numeric_grades) if numeric_grades else None,
            "maxGrade": max(numeric_grades) if numeric_grades else None,
            "countGrade2": grade_stats['countGrade2'],
            "countGrade3": grade_stats['countGrade3'],
            "countGrade4": grade_stats['countGrade4'],
            "countGrade5": grade_stats['countGrade5'],
            "countZachet": grade_stats['countZachet'],
            "countNejavka": grade_stats['countNejavka'],
            "countNezachet": grade_stats['countNezachet'],
        }

        subjects_list = [{"id": sid, "name": name} for name, sid in subjects_info]

        return {
            "summary": summary,
            "students": students_data,
            "subjects": subjects_list
        }

    @staticmethod
    def update_grade_stats(stats: dict, normalized_grade: str):
        """
        Обновляет счетчики статистики на основе нормализованной оценки.
        
        Добавляет числовые оценки в список для расчета среднего/мин/макс,
        а также инкрементирует соответствующие счетчики типов оценок.
        
        Args:
            stats (dict): Словарь со счетчиками и списком числовых оценок.
            normalized_grade (str): Нормализованное значение оценки ("2"-"5", "зачет", etc).
        """
        if normalized_grade in ["2", "3", "4", "5"]:
            grade_int = int(normalized_grade)
            stats['numeric_grades'].append(grade_int)
            stats[f'countGrade{grade_int}'] += 1
        elif normalized_grade == "зачет":
            stats['countZachet'] += 1
        elif normalized_grade == "незачет":
            stats['countNezachet'] += 1
        elif normalized_grade == "неявка":
            stats['countNejavka'] += 1