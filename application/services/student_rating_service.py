from datetime import datetime
from typing import Optional, List, Dict, Any
from django.db.models import Count
from application.models import Student, StudentResult, Attendance


class StudentRatingService:
    """
    Сервис для комплексной оценки успеваемости и поведения студентов.
    
    Предоставляет методы для:
    - Определения курса обучения на основе года поступления и текущей даты.
    - Расчета относительного процента посещаемости (относительно лидера группы).
    - Вычисления интегрального показателя активности студента.
    - Оценки риска отчисления на основе оценок, посещаемости и долгов.
    - Формирования рейтинговых списков студентов с детальной аналитикой.
    
    Все расчеты производятся динамически на основе данных из БД.
    """
    @staticmethod
    def calculate_course(year_of_admission: int) -> int:
        """
        Вычисляет текущий курс студента на основе года поступления.
        
        Логика:
        - Учебный год начинается 1 сентября.
        - Если текущий месяц < 9 (январь-август), курс = текущий год - год поступления.
        - Если текущий месяц >= 9 (сентябрь-декабрь), курс увеличивается на 1.
        
        Args:
            year_of_admission (int): Год поступления студента (например, 2023).
            
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
        
        Ожидает формат названия вида "Название-ГГ" (например, "КСм-23", "АСУб-21").
        
        Args:
            name (str): Название группы.
            
        Returns:
            Optional[int]: Полный год поступления (например, 2023) или None, если формат неверен.
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
    def normalize_grade_value(result_value: str) -> Optional[int]:
        """
        Преобразует строковое значение оценки в целое число.
        
        Обрабатывает только числовые оценки ("2", "3", "4", "5").
        Возвращает None для зачетов, неявок и других нечисловых значений.
        
        Args:
            result_value (str): Строковое значение оценки из БД.
            
        Returns:
            Optional[int]: Числовое значение оценки или None.
        """
        if not result_value:
            return None
        grade_clean = result_value.strip()
        if grade_clean in ["2", "3", "4", "5"]:
            return int(grade_clean)
        return None
    
    @classmethod
    def get_max_attendance_in_group(cls, student: Student) -> int:
        """
        Находит максимальное количество посещений среди всех студентов в группе данного студента.
        
        Используется как эталон (100%) для расчета относительной посещаемости.
        
        Args:
            student (Student): Объект студента, для группы которого ищется максимум.
            
        Returns:
            int: Максимальное количество посещенных занятий в группе.
        """
        if not student.group:
            return 0
        
        # Агрегируем посещения по студентам группы
        stats = Attendance.objects.filter(
            student__group=student.group
        ).values('student_id').annotate(
            visits=Count('lesson_id')
        )
        
        if not stats:
            return 0
            
        visits_counts = [item['visits'] for item in stats]
        return max(visits_counts) if visits_counts else 0

    @classmethod
    def calculate_attendance_percent(cls, student_id: int) -> float:
        """
        Рассчитывает процент посещаемости студента относительно самого активного студента в группе.
        
        Формула:
            (Посещения студента / Макс. посещения в группе) * 100
        
        Это позволяет оценивать активность студента внутри его коллектива без знания 
        общего количества запланированных пар.
        
        Args:
            student_id (int): ID студента.
            
        Returns:
            float: Процент посещаемости (0.0 - 100.0).
        """
        try:
            student = Student.objects.select_related('group').get(student_id=student_id)
        except Student.DoesNotExist:
            return 0.0

        attended_lessons = Attendance.objects.filter(student_id=student_id).count()
        
        if attended_lessons == 0:
            return 0.0

        max_visits_in_group = cls.get_max_attendance_in_group(student)
        
        if max_visits_in_group == 0:
            return 0.0

        percent = (attended_lessons / max_visits_in_group) * 100
        return min(round(percent, 2), 100.0)
    
    @classmethod
    def calculate_student_activity(cls, student_id: int) -> float:
        """
        Рассчитывает интегральный показатель активности студента по шкале от 0.0 до 5.0.
        
        Компоненты расчета:
        1. Успеваемость (вес 50%): Нормализованный средний балл.
        2. Посещаемость (вес 30%): Относительный процент посещаемости.
        3. Отсутствие долгов (вес 20%): Бонус начисляется, если у студента нет оценок "2", "Н/Я", "Не зачтено".
        
        Формула:
            Activity = (GradeScore * 0.5) + (AttendanceScore * 0.3) + (DebtBonus * 1.0)
        
        Args:
            student_id (int): ID студента.
            
        Returns:
            float: Показатель активности (0.0 - 5.0).
        """
        try:
            student = Student.objects.select_related('group').get(student_id=student_id)
        except Student.DoesNotExist:
            return 0.0

        # 1. Расчет среднего балла 
        grades_data = StudentResult.objects.filter(
            student_id=student_id
        ).select_related('result')
        
        numeric_grades = []
        has_debts = False
        
        for res in grades_data:
            val = res.result.result_value
            if val in ['2', 'Н/Я', 'Не зачтено']:
                has_debts = True
            norm = cls.normalize_grade_value(val)
            if norm is not None:
                numeric_grades.append(norm)
        
        avg_grade = sum(numeric_grades) / len(numeric_grades) if numeric_grades else 0.0
        grade_score = (avg_grade / 5.0) * 5.0  # Нормализация к шкале 0-5

        # 2. Расчет посещаемости (уже в процентах 0-100, переводим в шкалу 0-5)
        attendance_percent = cls.calculate_attendance_percent(student_id)
        attendance_score = (attendance_percent / 100.0) * 5.0

        # 3. Бонус за отсутствие долгов
        debt_bonus = 0.0
        if not has_debts and len(numeric_grades) > 0:
            debt_bonus = 1.0  # Добавляем до 1 балла, если нет долгов
            
        # Итоговая формула:
        # 50% успеваемость + 30% посещаемость + 20% отсутствие долгов
        # Максимально возможное значение: 2.5 + 1.5 + 1.0 = 5.0
        activity_score = (grade_score * 0.5) + (attendance_score * 0.3) + (debt_bonus * 0.2 * 5.0)

        return min(round(activity_score, 2), 5.0)

    @classmethod
    def calculate_dropout_risk(cls, student_id: int, avg_grade: float, attendance_percent: float, activity: float) -> float:
        """
        Рассчитывает вероятность отчисления студента (Risk Score) в диапазоне от 0.0 до 1.0.
        
        Факторы риска:
        1. Низкий средний балл (критический порог < 3.0).
        2. Низкая посещаемость (критический порог < 50% от лидера).
        3. Наличие академических задолженностей (наибольший вес).
        
        Весовые коэффициенты:
        - Долги: 50%
        - Оценки: 30%
        - Посещаемость: 20%
        
        Args:
            student_id (int): ID студента.
            avg_grade (float): Средний балл студента.
            attendance_percent (float): Процент посещаемости.
            activity (float): Показатель активности (используется косвенно или для логирования).
            
        Returns:
            float: Уровень риска (0.0 - низкий, 1.0 - критический).
        """
        # Подсчет долгов
        debt_count = StudentResult.objects.filter(
            student_id=student_id,
            result__result_value__in=['2', 'Н/Я', 'Не зачтено']
        ).count()
        
        # Компонент риска по оценкам (если ср.балл < 3, риск растет экспоненциально)
        grade_risk = 0.0
        if avg_grade > 0:
            if avg_grade >= 4.5:
                grade_risk = 0.0
            elif avg_grade >= 3.0:
                grade_risk = (4.5 - avg_grade) / 3.0 * 0.4 # Макс 0.2
            else:
                grade_risk = 0.4 + ((3.0 - avg_grade) / 3.0) * 0.4 # До 0.8

        # Компонент риска по посещаемости
        attendance_risk = 0.0
        if attendance_percent >= 80:
            attendance_risk = 0.0
        elif attendance_percent >= 50:
            attendance_risk = ((80 - attendance_percent) / 30.0) * 0.2
        else:
            attendance_risk = 0.2 + ((50 - attendance_percent) / 50.0) * 0.3 

        # Компонент риска по долгам (самый весомый)
        debt_risk = min(debt_count * 0.25, 1.0) # 4 долга = 100% риск

        # Взвешенная сумма
        # Долги имеют наибольший вес, так как это прямой путь к отчислению
        total_risk = (grade_risk * 0.3) + (attendance_risk * 0.2) + (debt_risk * 0.5)
        
        return max(0.0, min(1.0, round(total_risk, 2)))

    @classmethod
    def get_student_debts_details(cls, student_id: int) -> List[Dict[str, str]]:
        """
        Получает детальную информацию об академических задолженностях студента.
        
        Args:
            student_id (int): ID студента.
            
        Returns:
            List[Dict]: Список словарей с информацией о каждом долге:
                [
                    {
                        "discipline": "Название предмета",
                        "grade": "Оценка (2/Н/Я/Не зачтено)",
                        "type": "Тип долга (неуд/неявка/незачет)"
                    },
                    ...
                ]
        """
        debts = StudentResult.objects.filter(
            student_id=student_id,
            result__result_value__in=['2', 'Н/Я', 'Не зачтено']
        ).select_related('discipline', 'result')
        return [
            {
                "discipline": d.discipline.name,
                "grade": d.result.result_value,
                "type": cls.classify_debt_type(d.result.result_value)
            }
            for d in debts
        ]

    @staticmethod
    def classify_debt_type(grade_value: str) -> str:
        """
        Классифицирует тип задолженности по строковому значению оценки.
        
        Args:
            grade_value (str): Значение оценки.
            
        Returns:
            str: Человекочитаемый тип долга ('неуд', 'неявка', 'незачет', 'другой').
        """
        if grade_value == '2':
            return 'неуд'
        elif grade_value == 'Н/Я':
            return 'неявка'
        elif grade_value == 'Не зачтено':
            return 'незачет'
        return 'другой'

    @staticmethod
    def get_risk_level(risk_score: float) -> str:
        """
        Преобразует числовой показатель риска в текстовый уровень.
        
        Args:
            risk_score (float): Числовой риск (0.0 - 1.0).
            
        Returns:
            str: Уровень риска ("низкий", "средний", "высокий").
        """
        if risk_score < 0.3:
            return "низкий"
        elif risk_score < 0.7:
            return "средний"
        else:
            return "высокий"

    @classmethod
    def get_students_in_course(cls, course: int) -> List[int]:
        """
        Возвращает список ID студентов, обучающихся на указанном курсе.
        
        Использует логику определения года поступления из названия группы.
        Исключает студентов в академическом отпуске.
        
        Args:
            course (int): Номер курса.
            
        Returns:
            List[int]: Список идентификаторов студентов.
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
    def get_rating_data(
        cls,
        course: Optional[int] = None,
        group: Optional[str] = None,
        subject: Optional[str] = None,
        sort_by: str = 'rating',
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Основной метод сервиса. Формирует рейтинговый список студентов с полной аналитикой.
        
        Выполняет следующие шаги:
        1. Фильтрация студентов по курсу, группе или предмету.
        2. Расчет метрик для каждого студента (средний балл, активность, посещаемость).
        3. Вычисление композитного рейтинга.
        4. Сортировка и ограничение выборки (limit).
        5. Расчет риска отчисления и детализация долгов для топ-N студентов.
        6. Формирование ответа для графиков и таблиц.
        
        Args:
            course (int, optional): Фильтр по номеру курса.
            group (str, optional): Фильтр по названию группы.
            subject (str, optional): Фильтр по предмету (включает студентов, у которых есть оценка по этому предмету).
            sort_by (str): Критерий сортировки ('rating', 'performance', 'attendance', 'activity').
            limit (int): Максимальное количество возвращаемых записей.
            
        Returns:
            Dict[str, Any]: Структурированные данные:
                {
                    "chartData": [ ... ], # Данные для графиков
                    "students": [ ... ]   # Детальные данные для таблицы
                }
        """
        qs = Student.objects.select_related('group').filter(is_academic=False)

        # Фильтр по группе
        if group:
            qs = qs.filter(group__name=group)

        # Фильтр по курсу
        if course is not None:
            valid_ids = cls.get_students_in_course(course)
            qs = qs.filter(student_id__in=valid_ids)

        # Фильтр по предмету
        if subject:
            student_ids = StudentResult.objects.filter(
                discipline__name__icontains=subject
            ).values_list('student_id', flat=True).distinct()
            qs = qs.filter(student_id__in=student_ids)

        # Сбор данных
        students_data = []
        for student in qs:
            # Средний балл
            numeric_grades = []
            results = StudentResult.objects.filter(student=student).select_related('result')
            has_debts = False
            for result in results:
                val = result.result.result_value
                if val in ['2', 'Н/Я', 'Не зачтено']:
                    has_debts = True
                grade_val = cls.normalize_grade_value(val)
                if grade_val is not None:
                    numeric_grades.append(grade_val)
            
            avg_grade = sum(numeric_grades) / len(numeric_grades) if numeric_grades else 0.0

            # Активность и посещаемость 
            activity = cls.calculate_student_activity(student.student_id)
            attendance_percent = cls.calculate_attendance_percent(student.student_id)

            # Рейтинг (композитный показатель)
            # Используем новую активность как базу, плюс небольшой буст за абсолютные значения
            rating = (activity * 0.6) + (avg_grade * 0.4)
            # Нормализация к шкале 0-100 для удобства отображения
            rating = min(rating * 20, 100.0) 

            # Курс
            course_num = None
            if student.group and student.group.name:
                year = cls.extract_year_from_group_name(student.group.name)
                if year is not None:
                    course_num = cls.calculate_course(year)

            students_data.append({
                'student': student,
                'avg_grade': avg_grade,
                'activity': activity,
                'attendance_percent': attendance_percent,
                'rating': rating,
                'course': course_num,
                'has_debts': has_debts
            })

        # Сортировка
        sort_field_map = {
            'rating': 'rating',
            'performance': 'avg_grade',
            'attendance': 'attendance_percent',
            'activity': 'activity'
        }
        sort_key = sort_field_map.get(sort_by, 'rating')
        students_data.sort(key=lambda x: x[sort_key], reverse=True)
        students_data = students_data[:limit]

        chart_data = []
        students_response = []

        for data in students_data:
            student = data['student']
            
            # Пересчет риска с новыми входными данными
            dropout_risk = cls.calculate_dropout_risk(
                student.student_id,
                data['avg_grade'],
                data['attendance_percent'],
                data['activity']
            )
            
            debts_details = cls.get_student_debts_details(student.student_id)
            debt_count = len(debts_details)

            chart_data.append({
                'name': f"Студент {student.student_id}",
                'avgGrade': round(data['avg_grade'], 2),
                'activity': round(data['activity'], 2),
                'attendancePercent': round(data['attendance_percent'], 2)
            })

            students_response.append({
                'id': student.student_id,
                'name': f"Студент {student.student_id}", 
                'group': student.group.name if student.group else None,
                'course': data['course'],
                'avgGrade': round(data['avg_grade'], 2),
                'activity': round(data['activity'], 2),
                'attendancePercent': round(data['attendance_percent'], 2),
                'debtCount': debt_count,
                'debtsDetails': debts_details,
                'dropoutRisk': round(dropout_risk, 2),
                'rating': round(data['rating'], 2),
                'riskLevel': cls.get_risk_level(dropout_risk)
            })

        return {
            'chartData': chart_data,
            'students': students_response
        }