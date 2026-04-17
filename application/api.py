from rest_framework.viewsets import GenericViewSet
from rest_framework.mixins import ListModelMixin
from rest_framework.response import Response
from rest_framework import status
from rest_framework import mixins, viewsets
#from application.management.commands import analytics пока не трогаем аналитику
#тестовая строка для проверки, потом убрать
#test 09.04.26
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.core.management import call_command
import json
import os
import csv
from django.conf import settings
from .models import Student, StudentResult
from application.services.grade_statistics_service import GradeStatisticsService
from application.services.academic_performance_service import AcademicPerformanceService
from application.services.subject_statistics_service import SubjectStatisticsService
from application.services.student_rating_service import StudentRatingService

class GradesViewset(ListModelMixin, GenericViewSet):
    """
    ViewSet для получения агрегированной статистики оценок студентов.
    
    Предоставляет сводные данные об успеваемости: средний балл, распределение оценок,
    минимальные и максимальные значения, а также детализацию по каждому студенту.
    
    Использует сервис: GradeStatisticsService
    
    Параметры фильтрации (Query Parameters):
        - course (int, optional): Номер курса (1, 2, 3...).
        - group (str, optional): Точное название группы (например, "КСм-23").
        - subject (str, optional): Название предмета (поиск по подстроке).
        
    Пример запроса:
        GET /api/statistics/marks/?course=2&group=ИТПм-22
        
    Ответ содержит:
        - summary: Общая статистика (средний балл, кол-во оценок каждого типа).
        - students: Список студентов с их оценками по предметам.
        - subjects: Список предметов.
    """
    queryset = StudentResult.objects.select_related('student', 'discipline', 'result')
    
    def list(self, request, *args, **kwargs):
        course = request.query_params.get('course')
        group = request.query_params.get('group')
        subject = request.query_params.get('subject')
        
        try:
            course = int(course) if course is not None else None
        except ValueError:
            course = None

        data = GradeStatisticsService.get_statistics(
            course=course,
            group=group,
            subject=subject
        )
        return Response(data)
    
class AcademicPerformanceViewSet(ListModelMixin, GenericViewSet):
    """
    ViewSet для анализа академической успеваемости с фокусом на задолженности (долги).
    
    Предоставляет данные о количестве долгов у студентов, распределении должников
    и средней нагрузке по группам. Полезен для кураторов и деканатов.
    
    Использует сервис: AcademicPerformanceService
    
    Параметры фильтрации (Query Parameters):
        - group (str, optional): Точное название группы.
        - search (str, optional): Поисковый запрос. Может быть:
            - ID студента (число).
            - Часть названия группы (строка).
            
    Пример запроса:
        GET /api/academic/performance/?search=КСм
        GET /api/academic/performance/?group=АСУб-21&search=12345
        
    Ответ содержит:
        - debtsDistribution: Гистограмма распределения студентов по кол-ву долгов (0, 1, 2, 3+).
        - groupAverages: Среднее кол-во долгов на студента в разрезе групп.
        - students: Список студентов с деталями их долгов.
    """
    queryset = Student.objects.none()

    def list(self, request, *args, **kwargs):
        group = request.query_params.get('group')
        search = request.query_params.get('search', '').strip()

        data = AcademicPerformanceService.get_performance_data(
            group=group,
            search=search
        )
        return Response(data)

class SubjectStatisticsViewSet(ListModelMixin, GenericViewSet):
    """
    ViewSet для получения рейтинга и статистики по учебным дисциплинам.
    
    Анализирует успешность освоения предметов: средний балл, посещаемость,
    интегральный показатель активности и количество задолженностей.
    
    Использует сервис: SubjectStatisticsService
    
    Параметры фильтрации (Query Parameters):
        - course (int, optional): Номер курса.
        - subject (str, optional): Название предмета (поиск).
        - groups (str, optional): Список групп через запятую (напр., "КСм-23,ИТПм-23").
        - sortBy (str, optional): Критерий сортировки ('avg', 'max', 'count', 'activity'). По умолчанию 'avg'.
        - limit (int, optional): Количество возвращаемых топ-предметов. По умолчанию 5.
        
    Пример запроса:
        GET /api/statistics/subject/?course=3&sortBy=activity&limit=10
        
    Ответ содержит:
        - subjectStats: Общая статистика по выборке.
        - gradeDistributionBar: Распределение оценок (2,3,4,5).
        - bestSubjects: Топ предметов с метриками (avg, max, count, avgAttendance, avgActivity).
    """
    queryset = StudentResult.objects.select_related('student', 'discipline', 'result')

    def list(self, request, *args, **kwargs):
        course = request.query_params.get('course')
        subject = request.query_params.get('subject')
        groups_param = request.query_params.get('groups', '')
        sort_by = request.query_params.get('sortBy', 'avg')
        limit = int(request.query_params.get('limit', 5))

        try:
            course = int(course) if course is not None else None
        except ValueError:
            course = None

        groups = [g.strip() for g in groups_param.split(',')] if groups_param else []
        groups = [g for g in groups if g]  # убираем пустые

        data = SubjectStatisticsService.get_statistics(
            course=course,
            subject=subject,
            groups=groups,
            sort_by=sort_by,
            limit=limit
        )
        return Response(data)
    
class StudentRatingViewSet(ListModelMixin, GenericViewSet):
    """
    ViewSet для формирования рейтинга студентов на основе комплексной оценки.
    
    Рассчитывает индивидуальный рейтинг, учитывая средний балл, относительную посещаемость,
    активность и риск отчисления. Позволяет выявлять лидеров и студентов группы риска.
    
    Использует сервис: StudentRatingService
    
    Параметры фильтрации (Query Parameters):
        - course (int, optional): Номер курса.
        - group (str, optional): Название группы.
        - subject (str, optional): Фильтр по предмету (включает студентов, имеющих оценку по этому предмету).
        - sortBy (str, optional): Критерий сортировки ('rating', 'performance', 'attendance', 'activity'). По умолчанию 'rating'.
        - limit (int, optional): Количество студентов в выдаче. По умолчанию 10.
        
    Пример запроса:
        GET /api/student-rating/?course=2&sortBy=performance&limit=20
        
    Ответ содержит:
        - chartData: Данные для графиков (имя, avgGrade, activity, attendance).
        - students: Детальный список студентов с метриками:
            - avgGrade, activity, attendancePercent
            - debtCount, debtsDetails
            - dropoutRisk, riskLevel
            - rating
    """
    queryset = Student.objects.all().select_related('group')

    def list(self, request, *args, **kwargs):
        course = request.query_params.get('course')
        group = request.query_params.get('group')
        subject = request.query_params.get('subject')
        sort_by = request.query_params.get('sortBy', 'rating')
        limit = int(request.query_params.get('limit', 10) or 10)

        try:
            course = int(course) if course is not None else None
        except ValueError:
            course = None

        data = StudentRatingService.get_rating_data(
            course=course,
            group=group,
            subject=subject,
            sort_by=sort_by,
            limit=limit
        )
        return Response(data)


##################################################################################    
class AnalyticsTrainViewSet(viewsets.ViewSet):
    """
    ViewSet для запуска процесса кластеризации.
    
    Назначение:
    - Инициирует выполнение Django management команды 'generate_analytics'.
    - Команда собирает данные из БД, выполняет кластеризацию (KMeans) и сохраняет результат в JSON.
    
    Требования:
    - Доступно только авторизованным пользователям (IsAuthenticated).
    - Рекомендуется использовать для периодического обновления данных (не для каждого запроса пользователя).
    
    Методы:
        create (POST): Запуск процесса генерации.
    """
    permission_classes = [IsAuthenticated]

    def create(self, request):
        """
        Запускает management команду для пересчета аналитики.
        
        Процесс:
        1. Вызов call_command('generate_analytics').
        2. Ожидание завершения скрипта (синхронно).
        3. Сохранение результатов в файл media/analytics_cache/student_analytics.json.
        
        Returns:
            200 OK: {"message": "Аналитика успешно пересчитана и сохранена."}
            500 Error: {"error": "Описание ошибки"}
        """
        # Вызов management команды
        call_command('generate_analytics')
        return Response(
            {"message": "Аналитика успешно пересчитана и сохранена."},
            status=status.HTTP_200_OK
        )

class AnalyticsDataViewSet(viewsets.ViewSet):
    """
    ViewSet для получения готовых результатов кластеризации студентов.
    
    Назначение:
    - Читает предварительно сгенерированный JSON-файл из кэша.
    - Предоставляет данные для визуализации кластеров и статистики по группам.
    - Поддерживает фильтрацию по группе и получение данных конкретного студента.
    
    Требования:
    - Доступно только авторизованным пользователям.
    - Файл должен быть сгенерирован заранее через AnalyticsTrainViewSet.
    
    Методы:
        list (GET): Получение списка всех студентов с кластерами.
        retrieve (GET): Получение данных одного студента по ID.
    """
    permission_classes = [IsAuthenticated]
    
    def list(self, request):
        """
        Возвращает полный список студентов с результатами кластеризации.
        
        Query Parameters:
            - group (str, optional): Фильтр по названию группы.
            
        Логика:
        1. Проверка существования файла кэша.
        2. Чтение JSON.
        3. Применение фильтра по группе (если указан).
        4. Возврат данных.
        
        Returns:
            200 OK: JSON с данными (students, group_stats, total_students, clusters_count).
            404 Not Found: Если файл еще не сгенерирован.
        """
        file_name = 'student_analytics.json'
        relative_path = os.path.join('analytics_cache', file_name)
        file_path = os.path.join(settings.MEDIA_ROOT, relative_path)
        
        # Проверка существования файла
        if not os.path.exists(file_path):
            return Response(
                {"error": "Аналитика еще не сгенерирована. Запустите обучение модели (POST /api/analytics/train/)."},
                status=status.HTTP_404_NOT_FOUND
            )
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # фильтрация по параметрам запроса (группа, факультет)
        group_filter = request.query_params.get('group')
        if group_filter:
            # Фильтруем список студентов
            data['students'] = [
                s for s in data.get('students', []) 
                if s.get('group') == group_filter
            ]

            data['total_students'] = len(data['students'])
            
        return Response(data, status=status.HTTP_200_OK)

    def retrieve(self, request, pk=None):
        """
        Возвращает данные конкретного студента по его ID.
        
        Args:
            pk (str|int): ID студента (из URL).
            
        Логика:
        1. Проверка существования файла.
        2. Чтение JSON.
        3. Поиск студента в списке по полю 'student_id'.
        
        Returns:
            200 OK: Объект студента.
            404 Not Found: Если файл не найден или студент не найден в данных.
        """
        file_name = 'student_analytics.json'
        relative_path = os.path.join('analytics_cache', file_name)
        file_path = os.path.join(settings.MEDIA_ROOT, relative_path)

        if not os.path.exists(file_path):
            return Response({"error": "Data not generated"}, status=404)
            
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        student = next((s for s in data.get('students', []) if str(s['student_id']) == str(pk)), None)
        
        if not student:
            return Response({"error": "Student not found"}, status=404)
            
        return Response(student)
    
class GradePredictionTrainViewSet(viewsets.ViewSet):
    """
    ViewSet для запуска процесса обучения нейросетевой модели прогнозирования оценок (PyTorch).
    
    Назначение:
    - Предоставляет API эндпоинт для инициирования пайплайна машинного обучения.
    - Принимает параметры фильтрации (факультет, группа, курс) для выбора целевой выборки.
    - Вызывает Django management команду `generate_grade_predictions`, которая выполняет:
        1. Сбор данных из БД (оценки, посещаемость).
        2. Подготовку признаков (нормализация, расчет относительной посещаемости).
        3. Обучение модели GradeRegressor на данных старших курсов.
        4. Генерацию прогнозов для студентов указанного курса.
        5. Сохранение результатов в JSON.
    
    Требования:
    - Пользователь должен быть аутентифицирован (IsAuthenticated).
    - Наличие данных в БД для указанных параметров.
    - Установленные библиотеки PyTorch, Pandas, Scikit-learn.
    
    Методы:
        create (POST): Запуск процесса обучения и генерации прогнозов.
    """
    permission_classes = [IsAuthenticated]

    def create(self, request):
        """
        Обрабатывает POST-запрос для запуска обучения модели.
        
        Параметры передаются в теле запроса (JSON Body):
            - faculty (str): Полное название факультета (обязательно).
            - group_base (str): Базовая часть названия группы без года (обязательно, напр. "ИСТб").
            - course (int): Номер курса для прогнозирования (1, 2 или 3) (обязательно).
        
        Логика работы:
        1. Валидация наличия всех обязательных параметров.
        2. Преобразование параметра `course` в целое число.
        3. Синхронный вызов management команды `generate_grade_predictions`.
        4. Возврат статуса выполнения.
        
        Returns:
            Response (200 OK): {"message": "Прогнозирование для {group} (курс {course}) запущено и завершено."}
            Response (400 Bad Request): {"error": "Необходимы параметры: faculty, group_base, course"}
            Response (500 Internal Server Error): {"error": "Описание ошибки исполнения"}
            
        Пример запроса (JSON):
            {
                "faculty": "Институт информационных технологий и анализа данных",
                "group_base": "ИСТб",
                "course": 2
            }
        """
        faculty = request.data.get('faculty')
        group_base = request.data.get('group_base')
        course = request.data.get('course')
        # faculty = request.query_params.get('faculty')
        # group_base = request.query_params.get('group_base')
        # course = request.query_params.get('course')

        if not all([faculty, group_base, course]):
            return Response(
                {"error": "Необходимы параметры: faculty, group_base, course"},
                status=status.HTTP_400_BAD_REQUEST
            )

        course = int(course)
        call_command('generate_grade_predictions', 
                        faculty=faculty, 
                        group_base=group_base, 
                        course=course)
        
        return Response(
            {"message": f"Прогнозирование для {group_base} (курс {course}) запущено и завершено."},
            status=status.HTTP_200_OK
        )

class GradePredictionDataViewSet(viewsets.ViewSet):
    """
    ViewSet для получения результатов прогнозирования оценок.
    
    Назначение:
    - Предоставляет доступ к ранее сгенерированным прогнозам модели.
    - Читает данные из файлов, созданных командой `generate_grade_predictions`.
    - Поддерживает фильтрацию результатов по конкретному студенту.
    
    Требования:
    - Пользователь должен быть аутентифицирован.
    - Файл с прогнозами должен быть предварительно сгенерирован через `GradePredictionTrainViewSet`.
    - Путь к файлу формируется динамически на основе параметров запроса.
    
    Методы:
        list (GET): Получение списка прогнозов для группы/курса или конкретного студента.
    """
    permission_classes = [IsAuthenticated]

    def list(self, request):
        """
        Обрабатывает GET-запрос для получения данных прогнозов.
        
        Параметры передаются в строке запроса :
            - faculty (str): Название факультета (обязательно).
            - group_base (str): База названия группы (обязательно).
            - course (int): Номер курса (обязательно).
            - student_id (str, optional): ID конкретного студента для фильтрации результата.
        
        Логика работы:
        1. Валидация обязательных параметров.
        2. Формирование имени файла: `predictions_{faculty}_{group_base}_course{course}.json`.
        3. Проверка существования файла в директории `MEDIA_ROOT/prediction_cache/`.
        4. Чтение и десериализация JSON.
        5. Опциональная фильтрация списка по `student_id`.
        6. Возврат структурированного ответа.
        
        Returns:
            Response (200 OK): {
                "faculty": "...",
                "group_base": "...",
                "course": ...,
                "predictions": [ {...}, {...} ]
            }
            Response (400 Bad Request): При отсутствии обязательных параметров.
            Response (404 Not Found): Если файл с прогнозами еще не сгенерирован.
            Response (500 Internal Server Error): При ошибке чтения файла.
            
        Пример запроса:
            GET /api/predictions/data/?faculty=Институт...&group_base=ИСТб&course=2
            GET /api/predictions/data/?faculty=...&group_base=ИСТб&course=2&student_id=12345
        """
        faculty = request.query_params.get('faculty')
        group_base = request.query_params.get('group_base')
        course = request.query_params.get('course')

        if not all([faculty, group_base, course]):
            return Response(
                {"error": "Необходимы параметры: faculty, group_base, course"},
                status=status.HTTP_400_BAD_REQUEST
            )

        filename = f"predictions_{faculty.replace(' ', '_')}_{group_base}_course{course}.json"
        filepath = os.path.join(settings.MEDIA_ROOT, 'prediction_cache', filename)

        if not os.path.exists(filepath):
            return Response(
                {"error": "Прогноз еще не сгенерирован. Запустите обучение модели."},
                status=status.HTTP_404_NOT_FOUND
            )

        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Опциональная фильтрация по студенту
        student_id = request.query_params.get('student_id')
        if student_id:
            data = [s for s in data if str(s.get('mira_id')) == str(student_id)]

        return Response({
            "faculty": faculty,
            "group_base": group_base,
            "course": course,
            "predictions": data
        }, status=status.HTTP_200_OK)

class AcademicReturnsViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    ViewSet для получения статистики по возвратам из академических отпусков.
    
    Назначение:
    - Предоставляет API endpoint для получения статистики по студентам, 
      находящимся в академических отпусках
    - Анализирует статусы студентов (возвращены, отчислены, продолжают обучение)
    - Формирует отчет с распределением по статусам и детализацией по студентам
    
    Входные параметры:
    - Стандартные параметры DRF (пагинация, фильтрация)
    - Возможность фильтрации через backend filters (если настроены)
    
    Выходные данные:
    - JSON объект с двумя основными разделами:
      1. statusDistribution - статистика по статусам студентов
      2. students - детальная информация по студентам с завершенными отпусками
    """
    # # Добавляем обязательный queryset
    # queryset = Academ.objects.none()
    
    # def get_queryset(self):
    #     """
    #     Получает базовый queryset с выборкой всех записей об академотпусках.
        
    #     Возвращает:
    #     - QuerySet: Все записи об академических отпусках с предзагрузкой 
    #       связанных данных через select_related 
        
    #     Оптимизированные связи:
    #     - student → основная информация о студенте
    #     - student__group → текущая группа студента
    #     - previous_group → предыдущая группа (до академа)
    #     - relevant_group → актуальная группа для возврата
    #     """
    #     return Academ.objects.select_related(
    #         'student',
    #         'student__group',
    #         'previous_group',
    #         'relevant_group'
    #     ).all()
    
    # def determine_status(self, academ):
    #     """
    #     Определяет текущий статус студента на основе данных об академическом отпуске.
        
    #     Параметры:
    #     - academ: объект модели Academ - запись об академическом отпуске
        
    #     Возвращает:
    #     - str: текстовое описание статуса студента:
    #       * "Продолжает обучение" - если отпуск еще продолжается или нет даты окончания
    #       * "Возвращён" - если отпуск завершен и студент прикреплен к группе
    #       * "Отчислен" - если отпуск завершен, но студент не прикреплен к группе
        
    #     Логика определения:
    #     1. Если нет даты окончания отпуска → статус "Продолжает обучение"
    #     2. Если дата окончания прошла:
    #        - Есть текущая группа → "Возвращён"
    #        - Нет текущей группы → "Отчислен"
    #     3. Если дата окончания еще не наступила → "Продолжает обучение"
    #     """
    #     if not academ.end_date:
    #         return "Продолжает обучение"
        
    #     if academ.end_date < timezone.now().date():
    #         if academ.student.group:
    #             return "Возвращён"
    #         else:
    #             return "Отчислен"
    #     return "Продолжает обучение"
    
    # def list(self, request, *args, **kwargs):
    #     """
    #     Обрабатывает GET-запрос для получения статистики по возвратам.
        
    #     Входные параметры:
    #     - request: HTTP-запрос (может содержать параметры фильтрации)
        
    #     Выходные данные:
    #     - Response: JSON объект с структурой:
    #       {
    #         "statusDistribution": {
    #             "Отчислен": int,
    #             "Возвращён": int, 
    #             "Продолжает обучение": int
    #         },
    #         "students": [
    #             {
    #                 "id": int,           # ID студента
    #                 "name": str,         # ФИО студента
    #                 "group": str,        # Название группы
    #                 "returnDate": str,   # Дата возврата (YYYY-MM-DD)
    #                 "status": str        # Статус студента
    #             },
    #             ...
    #         ]
    #       }
        
    #     Особенности:
    #     - В раздел students включаются только записи с заполненной датой окончания отпуска
    #     - Студенты сортируются по дате возврата (сначала новые)
    #     - Используется фильтрация через DRF filters (если настроены)
    #     """
    #     # Получаем отфильтрованный queryset
    #     academ_records = self.filter_queryset(self.get_queryset())
        
    #     # Подготовка данных
    #     status_counts = {
    #         "Отчислен": 0,
    #         "Возвращён": 0,
    #         "Продолжает обучение": 0
    #     }
        
    #     students_data = []
        
    #     for academ in academ_records:
    #         status = self.determine_status(academ)
    #         status_counts[status] += 1
            
    #         # Добавляем в список только завершенные отпуска (с датой окончания)
    #         if academ.end_date:
    #             students_data.append({
    #                 "id": academ.student.student_id,
    #                 "name": academ.student.name,
    #                 "group": academ.relevant_group.title if academ.relevant_group else 
    #                         (academ.student.group.title if academ.student.group else None),
    #                 "returnDate": academ.end_date.strftime("%Y-%m-%d"),
    #                 "status": status
    #             })
        
    #     # Сортируем студентов по дате возвращения (новые сверху)
    #     students_data.sort(key=lambda x: x["returnDate"], reverse=True)
        
    #     return Response({
    #         "statusDistribution": status_counts,
    #         "students": students_data
    #     })


