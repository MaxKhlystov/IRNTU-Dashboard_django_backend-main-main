from collections import defaultdict
from django.db.models import Q, Count
from application.models import Student, StudentResult, StudentGroup

class AcademicPerformanceService:
    """
    Сервис для анализа академической успеваемости студентов, 
    фокусирующийся на выявлении и статистике академических задолженностей (долгов).
    
    Предоставляет методы для:
    - Фильтрации студентов по наличию долгов.
    - Расчета распределения должников.
    - Агрегации статистики по учебным группам.
    - Получения детальной информации о долгах конкретного студента.
    """
    @staticmethod
    def get_debts_filter():
        """
        Возвращает объект Q для фильтрации записей с академическими задолженностями.
        
        Критерии долга:
        - Оценка '2' (неудовлетворительно)
        - 'Н/Я' (неявка)
        - 'Не зачтено'
        
        Returns:
            django.db.models.Q: Объект запроса для использования в filter().
        """
        return Q(studentresult__result__result_value__in=['2', 'Н/Я', 'Не зачтено'])

    @classmethod
    def get_queryset(cls):
        """
        Формирует базовый QuerySet студентов для анализа.
        
        Логика:
        1. Выбирает всех активных студентов (исключая тех, кто в академическом отпуске).
        2. Оптимизирует запрос, подгружая связанную группу (select_related).
        3. Аннотирует каждого студента количеством долгов (debt_count) через агрегацию Count 
           с использованием фильтра get_debts_filter().
        4. Сортирует результат по ID студента.
        
        Returns:
            django.db.models.QuerySet: QuerySet объектов Student с аннотацией 'debt_count'.
        """
        return Student.objects.select_related('group').filter(
            is_academic=False
        ).annotate(
            debt_count=Count('studentresult', filter=cls.get_debts_filter())
        ).order_by('student_id')

    @classmethod
    def apply_filters(cls, queryset, group: str = None, search: str = None):
        """
        Применяет дополнительные фильтры к QuerySet студентов.
        
        Args:
            queryset (django.db.models.QuerySet): Базовый набор данных.
            group (str, optional): Название группы для точной фильтрации.
            search (str, optional): Поисковый запрос. Может быть:
                - Целым числом (ID студента).
                - Строкой (часть названия группы).
        
        Returns:
            django.db.models.QuerySet: Отфильтрованный набор данных.
        """
        if group:
            queryset = queryset.filter(group__name=group)
        if search:
            try:
                student_id = int(search)
                queryset = queryset.filter(student_id=student_id)
            except ValueError:
                # Поиск по названию группы
                queryset = queryset.filter(group__name__icontains=search)
        return queryset

    @classmethod
    def get_debt_distribution(cls, students):
        """
        Рассчитывает распределение студентов в зависимости от количества имеющихся у них долгов.
        
        Категории распределения:
        - zero_debts: Студенты без долгов.
        - one_debt: Студенты с 1 долгом.
        - two_debts: Студенты с 2 долгами.
        - three_plus_debts: Студенты с 3 и более долгами.
        
        Args:
            students (list): Список объектов Student (с аннотацией debt_count).
        
        Returns:
            dict: Словарь с количеством студентов в каждой категории.
                {
                    'zero_debts': int,
                    'one_debt': int,
                    'two_debts': int,
                    'three_plus_debts': int
                }
        """
        dist = {
            'zero_debts': 0,
            'one_debt': 0,
            'two_debts': 0,
            'three_plus_debts': 0
        }
        for student in students:
            c = student.debt_count
            if c == 0:
                dist['zero_debts'] += 1
            elif c == 1:
                dist['one_debt'] += 1
            elif c == 2:
                dist['two_debts'] += 1
            else:
                dist['three_plus_debts'] += 1
        return dist

    @classmethod
    def calculate_group_stats(cls, students):
        """
        Вычисляет среднее количество долгов на студента в разрезе учебных групп.
        
        Логика:
        1. Группирует переданных студентов по ID группы.
        2. Загружает названия групп из БД одним запросом.
        3. Для каждой группы считает сумму долгов и делит на количество студентов.
        4. Сортирует результат по названию группы.
        
        Args:
            students (list): Список объектов Student.
        
        Returns:
            list[dict]: Список словарей со статистикой:
                [
                    {"group": "Название группы", "avgDebts": float},
                    ...
                ]
        """
        # Группируем студентов по group_id
        groups = defaultdict(list)
        for s in students:
            if s.group_id:
                groups[s.group_id].append(s)

        if not groups:
            return []

        # Получаем названия групп
        group_ids = list(groups.keys())
        group_names = {
            g.group_id: g.name
            for g in StudentGroup.objects.filter(group_id__in=group_ids)
        }

        stats = []
        for gid, student_list in groups.items():
            total_debts = sum(s.debt_count for s in student_list)
            avg = total_debts / len(student_list)
            stats.append({
                "group": group_names.get(gid, f"Группа {gid}"),
                "avgDebts": round(float(avg), 1)
            })

        stats.sort(key=lambda x: x['group'])
        return stats

    @classmethod
    def get_student_debts_details(cls, student_id):
        """
        Получает детальную информацию о задолженностях конкретного студента.
        
        Args:
            student_id (int): Уникальный идентификатор студента.
        
        Returns:
            list[dict]: Список словарей с информацией о каждом долге:
                [
                    {"discipline": "Название предмета", "grade": "Оценка (2/Н/Я/Не зачтено)"},
                    ...
                ]
        """
        debts = StudentResult.objects.filter(
            student_id=student_id,
            result__result_value__in=['2', 'Н/Я', 'Не зачтено']
        ).select_related('discipline', 'result')
        return [
            {"discipline": d.discipline.name, "grade": d.result.result_value}
            for d in debts
        ]

    @classmethod
    def get_performance_data(cls, group: str = None, search: str = None):
        """
        Основной метод сервиса. Собирает и возвращает полный набор данных 
        об академической успеваемости для отображения в интерфейсе.
        
        Выполняет следующие шаги:
        1. Формирует базовый запрос студентов с подсчетом долгов.
        2. Применяет фильтры (по группе или поиску).
        3. Извлекает данные в память (один SQL запрос).
        4. Генерирует список студентов с деталями долгов.
        5. Рассчитывает общее распределение должников.
        6. Рассчитывает средние показатели по группам.
        
        Args:
            group (str, optional): Фильтр по названию группы.
            search (str, optional): Поисковый запрос (ID студента или часть названия группы).
        
        Returns:
            dict: Структурированные данные для API:
                {
                    "debtsDistribution": {
                        "0": int, "1": int, "2": int, "3plus": int
                    },
                    "groupAverages": [
                        {"group": str, "avgDebts": float}, ...
                    ],
                    "students": [
                        {
                            "id": int,
                            "group": str,
                            "debts": int,
                            "debtsDetails": [...]
                        }, ...
                    ]
                }
        """
        queryset = cls.get_queryset()
        filtered_qs = cls.apply_filters(queryset, group=group, search=search)

        # Выполняем запрос один раз
        students = list(filtered_qs)

        # Подготавливаем данные
        students_data = []
        for s in students:
            students_data.append({
                "id": s.student_id,
                "group": s.group.name if s.group else None,
                "debts": s.debt_count,
                "debtsDetails": cls.get_student_debts_details(s.student_id)
            })

        debt_dist = cls.get_debt_distribution(students)
        group_averages = cls.calculate_group_stats(students)

        return {
            "debtsDistribution": {
                "0": debt_dist['zero_debts'],
                "1": debt_dist['one_debt'],
                "2": debt_dist['two_debts'],
                "3plus": debt_dist['three_plus_debts']
            },
            "groupAverages": group_averages,
            "students": students_data
        }