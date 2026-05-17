from datetime import datetime
import time
from django.core.cache import cache
from typing import Optional, List, Dict, Any
from application.models import Student, StudentResult, Attendance
from django.db.models import Avg, Count, Q, Value, FloatField, Case, When
from django.db.models.functions import Cast
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
import traceback


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
        Улучшенная логика с более реалистичными значениями.
        """
        # Подсчет долгов
        debt_count = StudentResult.objects.filter(
            student_id=student_id,
            result__result_value__in=['2', 'Н/Я', 'Не зачтено']
        ).count()
        
        # Базовый риск (0-1)
        # ДОЛГИ - самый важный фактор (вес 50%)
        if debt_count == 0:
            debt_risk = 0.0
        elif debt_count == 1:
            debt_risk = 0.4
        elif debt_count == 2:
            debt_risk = 0.7
        else:
            debt_risk = 1.0
        
        # ОЦЕНКИ - второй по важности фактор (вес 30%)
        if avg_grade >= 4.5:
            grade_risk = 0.0
        elif avg_grade >= 4.0:
            grade_risk = 0.1
        elif avg_grade >= 3.5:
            grade_risk = 0.2
        elif avg_grade >= 3.0:
            grade_risk = 0.35
        elif avg_grade >= 2.5:
            grade_risk = 0.55
        elif avg_grade > 0:
            grade_risk = 0.75
        else:
            grade_risk = 0.3  # Нет оценок - средний риск
        
        # ПОСЕЩАЕМОСТЬ - третий фактор (вес 20%)
        if attendance_percent >= 90:
            attendance_risk = 0.0
        elif attendance_percent >= 75:
            attendance_risk = 0.15
        elif attendance_percent >= 50:
            attendance_risk = 0.35
        elif attendance_percent >= 25:
            attendance_risk = 0.6
        else:
            attendance_risk = 0.85
        
        # Взвешенная сумма
        total_risk = (grade_risk * 0.3) + (attendance_risk * 0.2) + (debt_risk * 0.5)
        
        # Корректировка для крайних случаев
        if debt_count == 0 and avg_grade >= 4.0 and attendance_percent >= 75:
            total_risk = min(total_risk, 0.15)  # Отличники с хорошей посещаемостью
        elif debt_count >= 2 and avg_grade < 3.0:
            total_risk = max(total_risk, 0.6)   # Должники с плохими оценками
        elif debt_count == 0 and attendance_percent < 30:
            total_risk = max(total_risk, 0.3)   # Прогулы даже без долгов
        
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
        elif risk_score < 0.65:
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
    def get_rating_data(cls, course=None, group=None, subject=None, sort_by='rating', limit=10, page=1):
        """
        Основной метод сервиса. Формирует рейтинговый список студентов с полной аналитикой.
        Теперь с поддержкой пагинации.
        
        Args:
            course: Фильтр по курсу
            group: Фильтр по группе
            subject: Фильтр по предмету
            sort_by: Критерий сортировки
            limit: Количество записей на страницу
            page: Номер страницы (1-based)
        """
        # Кэшируем только данные без пагинации (общий список)
        cache_key = f"rating_data:{course}:{group}:{subject}:{sort_by}"
        cached_data = cache.get(cache_key)
        
        if cached_data is None:
            # Получаем все данные (без пагинации)
            try:
                qs = Student.objects.filter(is_academic=False)
                if group:
                    qs = qs.filter(group__name=group)
                
                # Фильтр по курсу (если указан)
                if course is not None:
                    valid_ids = cls.get_students_in_course(course)
                    qs = qs.filter(student_id__in=valid_ids)
                
                # Фильтр по предмету (если указан)
                if subject:
                    student_ids_with_subject = StudentResult.objects.filter(
                        discipline__name__icontains=subject
                    ).values_list('student_id', flat=True).distinct()
                    qs = qs.filter(student_id__in=student_ids_with_subject)
                
                student_ids = list(qs.values_list('student_id', flat=True))
                if not student_ids:
                    return {'chartData': [], 'students': [], 'total': 0, 'page': page, 'total_pages': 0}
                
                # Агрегация данных (как раньше)
                grades_agg = StudentResult.objects.filter(
                    student_id__in=student_ids
                ).values('student_id').annotate(
                    avg_grade=Avg(
                        Case(
                            When(result__result_value__in=['2','3','4','5'], 
                                then=Cast('result__result_value', FloatField())),
                            default=None,
                            output_field=FloatField()
                        )
                    ),
                    debt_count=Count('student_id', filter=Q(result__result_value__in=['2', 'Н/Я', 'Не зачтено']))
                )
                
                attendance_agg = Attendance.objects.filter(
                    student_id__in=student_ids
                ).values('student_id').annotate(
                    total_visits=Count('lesson_id')
                )
                
                max_att_by_group = dict(
                    Attendance.objects.filter(
                        student__group__isnull=False,
                        student_id__in=student_ids
                    ).values('student__group__name').annotate(
                        max_visits=Count('lesson_id')
                    ).values_list('student__group__name', 'max_visits')
                )
                
                grades_dict = {g['student_id']: {'avg': float(g['avg_grade'] or 0), 'debts': g['debt_count']} 
                            for g in grades_agg}
                attendance_dict = {a['student_id']: a['total_visits'] for a in attendance_agg}
                
                results = []
                for student in qs.select_related('group'):
                    sid = student.student_id
                    group_name = student.group.name if student.group else 'Неизвестно'
                    
                    avg_grade = grades_dict.get(sid, {}).get('avg', 0)
                    debt_count = grades_dict.get(sid, {}).get('debts', 0)
                    total_visits = attendance_dict.get(sid, 0)
                    max_visits = max_att_by_group.get(group_name, 1)
                    
                    attendance_percent = min((total_visits / max_visits) * 100, 100) if max_visits > 0 else 0
                    has_debts = debt_count > 0
                    
                    # Расчет активности
                    grade_score = avg_grade
                    attendance_score = attendance_percent / 100 * 5
                    debt_bonus = 1.0 if (not has_debts and avg_grade > 0) else 0
                    activity = (grade_score * 0.5) + (attendance_score * 0.3) + (debt_bonus * 1.0)
                    
                    # Рейтинг
                    rating = min(activity * 20, 100)
                    
                    # Определение курса
                    course_num = None
                    if group_name and '-' in group_name:
                        try:
                            year_suffix = int(group_name.split('-')[1][:2])
                            course_num = cls.calculate_course(2000 + year_suffix)
                        except:
                            pass
                    
                    # Расчет риска
                    dropout_risk = cls.calculate_dropout_risk(sid, avg_grade, attendance_percent, activity)
                    status = cls.get_student_status(sid, avg_grade, attendance_percent, debt_count, dropout_risk)
                    results.append({
                        'id': sid,
                        'name': f"Студент {sid}",
                        'group': group_name,
                        'course': course_num,
                        'avgGrade': round(avg_grade, 2),
                        'activity': round(activity, 2),
                        'attendancePercent': round(attendance_percent, 2),
                        'rating': round(rating, 2),
                        'debtCount': debt_count,
                        'debtsDetails': cls.get_student_debts_details(sid) if debt_count > 0 else [],
                        'dropoutRisk': dropout_risk,
                        'riskLevel': cls.get_risk_level(dropout_risk),
                        'status' : status
                    })
                
                # Сортировка
                sort_map = {'rating': 'rating', 'performance': 'avgGrade', 
                            'attendance': 'attendancePercent', 'activity': 'activity'}
                results.sort(key=lambda x: x[sort_map.get(sort_by, 'rating')], reverse=True)
                
                # Сохраняем в кэш (без пагинации, на 10 минут)
                cached_data = results
                cache.set(cache_key, results, 600)  # 10 минут
                
            except Exception as e:
                import traceback
                traceback.print_exc()
                return {'chartData': [], 'students': [], 'total': 0, 'page': page, 'total_pages': 0}
        else:
            results = cached_data
        
        # Пагинация
        total = len(results)
        total_pages = (total + limit - 1) // limit if limit > 0 else 1
        
        # Получаем нужную страницу
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paged_results = results[start_idx:end_idx]
        
        # Данные для графиков (всегда берем топ-10 из отсортированного списка)
        chart_data = results[:10] if len(results) > 10 else results
        
        return {
            'chartData': chart_data,
            'students': paged_results,
            'total': total,
            'page': page,
            'total_pages': total_pages,
            'limit': limit
        }
    @classmethod
    def get_student_status(cls, student_id: int, avg_grade: float, attendance_percent: float, debt_count: int, dropout_risk: float) -> str:
        """
        Определяет статус студента на основе реальных данных.
        
        Возможные статусы:
        - "Отличник": средний балл >= 4.5, посещаемость >= 80%, нет долгов
        - "Хорошист": средний балл >= 4.0, посещаемость >= 70%, нет долгов
        - "Зона риска": риск отчисления > 0.5 ИЛИ есть долги
        - "Прогульщик": посещаемость < 50%, но нет долгов
        - "Троечник": средний балл < 4.0, но >= 3.0
        - "Должник": есть долги (2, Н/Я, Не зачтено)
        - "Нужно подтянуть": средний балл < 3.0
        """
        if debt_count > 0:
            return "Должник"
        
        if dropout_risk > 0.6:
            return "Зона риска"
        
        if avg_grade >= 4.5 and attendance_percent >= 80:
            return "Отличник"
        
        if avg_grade >= 4.0 and attendance_percent >= 70:
            return "Хорошист"
        
        if attendance_percent < 50:
            return "Прогульщик"
        
        if avg_grade >= 3.0:
            return "Троечник"
        
        if avg_grade < 3.0 and avg_grade > 0:
            return "Нужно подтянуть"
        
        return "Нет данных"
    # #@classmethod
    # def get_rating_data(
    #     cls,
    #     course: Optional[int] = None,
    #     group: Optional[str] = None,
    #     subject: Optional[str] = None,
    #     sort_by: str = 'rating',
    #     limit: int = 10
    # ) -> Dict[str, Any]:
    #     """
    #     Основной метод сервиса. Формирует рейтинговый список студентов с полной аналитикой.
        
    #     Выполняет следующие шаги:
    #     1. Фильтрация студентов по курсу, группе или предмету.
    #     2. Расчет метрик для каждого студента (средний балл, активность, посещаемость).
    #     3. Вычисление композитного рейтинга.
    #     4. Сортировка и ограничение выборки (limit).
    #     5. Расчет риска отчисления и детализация долгов для топ-N студентов.
    #     6. Формирование ответа для графиков и таблиц.
        
    #     Args:
    #         course (int, optional): Фильтр по номеру курса.
    #         group (str, optional): Фильтр по названию группы.
    #         subject (str, optional): Фильтр по предмету (включает студентов, у которых есть оценка по этому предмету).
    #         sort_by (str): Критерий сортировки ('rating', 'performance', 'attendance', 'activity').
    #         limit (int): Максимальное количество возвращаемых записей.
            
    #     Returns:
    #         Dict[str, Any]: Структурированные данные:
    #             {
    #                 "chartData": [ ... ], # Данные для графиков
    #                 "students": [ ... ]   # Детальные данные для таблицы
    #             }
    #     """
    #     qs = Student.objects.select_related('group').filter(is_academic=False)

    #     # Фильтр по группе
    #     if group:
    #         qs = qs.filter(group__name=group)

    #     # Фильтр по курсу
    #     if course is not None:
    #         valid_ids = cls.get_students_in_course(course)
    #         qs = qs.filter(student_id__in=valid_ids)

    #     # Фильтр по предмету
    #     if subject:
    #         student_ids = StudentResult.objects.filter(
    #             discipline__name__icontains=subject
    #         ).values_list('student_id', flat=True).distinct()
    #         qs = qs.filter(student_id__in=student_ids)

    #     # Сбор данных
    #     students_data = []
    #     for student in qs:
    #         # Средний балл
    #         numeric_grades = []
    #         results = StudentResult.objects.filter(student=student).select_related('result')
    #         has_debts = False
    #         for result in results:
    #             val = result.result.result_value
    #             if val in ['2', 'Н/Я', 'Не зачтено']:
    #                 has_debts = True
    #             grade_val = cls.normalize_grade_value(val)
    #             if grade_val is not None:
    #                 numeric_grades.append(grade_val)
            
    #         avg_grade = sum(numeric_grades) / len(numeric_grades) if numeric_grades else 0.0

    #         # Активность и посещаемость 
    #         activity = cls.calculate_student_activity(student.student_id)
    #         attendance_percent = cls.calculate_attendance_percent(student.student_id)

    #         # Рейтинг (композитный показатель)
    #         # Используем новую активность как базу, плюс небольшой буст за абсолютные значения
    #         rating = (activity * 0.6) + (avg_grade * 0.4)
    #         # Нормализация к шкале 0-100 для удобства отображения
    #         rating = min(rating * 20, 100.0) 

    #         # Курс
    #         course_num = None
    #         if student.group and student.group.name:
    #             year = cls.extract_year_from_group_name(student.group.name)
    #             if year is not None:
    #                 course_num = cls.calculate_course(year)

    #         students_data.append({
    #             'student': student,
    #             'avg_grade': avg_grade,
    #             'activity': activity,
    #             'attendance_percent': attendance_percent,
    #             'rating': rating,
    #             'course': course_num,
    #             'has_debts': has_debts
    #         })

    #     # Сортировка
    #     sort_field_map = {
    #         'rating': 'rating',
    #         'performance': 'avg_grade',
    #         'attendance': 'attendance_percent',
    #         'activity': 'activity'
    #     }
    #     sort_key = sort_field_map.get(sort_by, 'rating')
    #     students_data.sort(key=lambda x: x[sort_key], reverse=True)
    #     students_data = students_data[:limit]

    #     chart_data = []
    #     students_response = []

    #     for data in students_data:
    #         student = data['student']
            
    #         # Пересчет риска с новыми входными данными
    #         dropout_risk = cls.calculate_dropout_risk(
    #             student.student_id,
    #             data['avg_grade'],
    #             data['attendance_percent'],
    #             data['activity']
    #         )
            
    #         debts_details = cls.get_student_debts_details(student.student_id)
    #         debt_count = len(debts_details)

    #         chart_data.append({
    #             'name': f"Студент {student.student_id}",
    #             'avgGrade': round(data['avg_grade'], 2),
    #             'activity': round(data['activity'], 2),
    #             'attendancePercent': round(data['attendance_percent'], 2)
    #         })

    #         students_response.append({
    #             'id': student.student_id,
    #             'name': f"Студент {student.student_id}", 
    #             'group': student.group.name if student.group else None,
    #             'course': data['course'],
    #             'avgGrade': round(data['avg_grade'], 2),
    #             'activity': round(data['activity'], 2),
    #             'attendancePercent': round(data['attendance_percent'], 2),
    #             'debtCount': debt_count,
    #             'debtsDetails': debts_details,
    #             'dropoutRisk': round(dropout_risk, 2),
    #             'rating': round(data['rating'], 2),
    #             'riskLevel': cls.get_risk_level(dropout_risk)
    #         })

    #     return {
    #         'chartData': chart_data,
    #         'students': students_response
    #     }