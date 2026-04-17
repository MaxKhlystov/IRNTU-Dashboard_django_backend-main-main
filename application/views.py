from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django_filters.rest_framework import DjangoFilterBackend
from .permissions import IsStaffOrSuperUser
from .models import (
    Faculty, Speciality, StudentGroup, Student,
    Discipline, ResultType, StudentResult, Attendance, Administrator
)
from .serializers import (
    LoginSerializer, RegisterSerializer,
    FacultySerializer, SpecialitySerializer, StudentGroupSerializer,
    StudentSerializer, DisciplineSerializer, ResultTypeSerializer,
    StudentResultSerializer, AttendanceSerializer
)

class RegisterView(APIView):
    """
    Эндпоинт для регистрации нового администратора системы.
    
    Доступен любому пользователю (без аутентификации).
    Создает учетную запись с правами администратора на основе переданных данных.
    
    Методы:
        post: Обработка запроса на создание пользователя.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        """
        Регистрирует нового администратора.
        
        Ожидаемые данные (JSON):
            - email: Строка (уникальный email)
            - password: Строка (пароль)
            - дополнительные поля согласно RegisterSerializer
        
        Возвращает:
            201 Created: {'message': 'Administrator created successfully!'}
            400 Bad Request: {'errors': {...}} (если данные невалидны)
        """
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({'message': 'Administrator created successfully!'}, status=201)
        return Response(serializer.errors, status=400)


class LoginView(APIView):
    """
    Эндпоинт для аутентификации пользователя и получения JWT токенов.
    
    При успешном входе устанавливает HttpOnly cookie с access токеном
    и возвращает пару токенов (access и refresh) в теле ответа.
    
    Методы:
        post: Обработка запроса на вход.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        """
        Выполняет вход пользователя по email и паролю.
        
        Ожидаемые данные (JSON):
            - email: Строка
            - password: Строка
        
        Логика:
            1. Валидация входных данных.
            2. Проверка учетных данных через Django authenticate.
            3. Генерация JWT токенов.
            4. Установка cookie 'access_token' (HttpOnly, SameSite=Lax).
        
        Возвращает:
            200 OK: {
                "refresh": "<refresh_token>",
                "access": "<access_token>"
            } + Cookie
            401 Unauthorized: {"error": "Неверные данные"}
            400 Bad Request: Ошибки валидации
        """
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = authenticate(
                email=serializer.validated_data['email'],
                password=serializer.validated_data['password']
            )
            if user:
                refresh = RefreshToken.for_user(user)
                access_token = str(refresh.access_token)
                response = Response({
                    'refresh': str(refresh),
                    'access': access_token
                })
                response.set_cookie(
                    key="access_token",
                    value=access_token,
                    httponly=True,
                    samesite='Lax',
                    secure=False
                )
                return response
            return Response({"error": "Неверные данные"}, status=401)
        return Response(serializer.errors, status=400)


class CheckPermissionsView(APIView):
    """
    Эндпоинт для проверки прав доступа текущего аутентифицированного пользователя.
    
    Используется для динамического построения интерфейса на фронтенде
    в зависимости от разрешений пользователя.
    
    Требуется аутентификация.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Возвращает список всех разрешений (permissions) текущего пользователя.
        
        Возвращает:
            200 OK: {
                "permissions": [...]
            }
        """
        return Response({
            "permissions": list(request.user.get_all_permissions())
        })

# ViewSets для справочников (только чтение)
# Доступно только для персонала (Staff) и суперпользователей (SuperUser)
class FacultyViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Набор представлений для просмотра списка факультетов.
    
    Доступ: Только для сотрудников и администраторов.
    Операции: List, Retrieve (только чтение).
    
    Параметры URL:
        lookup_field: faculty_id (INTEGER)
    """
    queryset = Faculty.objects.all()
    serializer_class = FacultySerializer
    permission_classes = [IsStaffOrSuperUser]
    lookup_field = 'faculty_id'


class SpecialityViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Набор представлений для просмотра специальностей.
    
    Данные включают связанную информацию о факультете (select_related).
    Доступ: Только для сотрудников и администраторов.
    
    Параметры URL:
        lookup_field: speciality_id (INTEGER)
    """
    queryset = Speciality.objects.select_related('faculty').all()
    serializer_class = SpecialitySerializer
    permission_classes = [IsStaffOrSuperUser]
    lookup_field = 'speciality_id'


class StudentGroupViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Набор представлений для просмотра учебных групп.
    
    Оптимизированный запрос: подгружает специальность и факультет.
    Доступ: Только для сотрудников и администраторов.
    
    Параметры URL:
        lookup_field: group_id (INTEGER)
    """
    queryset = StudentGroup.objects.select_related('speciality__faculty').all()
    serializer_class = StudentGroupSerializer
    permission_classes = [IsStaffOrSuperUser]
    lookup_field = 'group_id'


class StudentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Набор представлений для просмотра карточек студентов.
    
    Оптимизированный запрос: подгружает всю иерархию (Группа -> Специальность -> Факультет).
    Доступ: Только для сотрудников и администраторов.
    
    Параметры URL:
        lookup_field: student_id (INTEGER)
    """
    queryset = Student.objects.select_related('group__speciality__faculty').all()
    serializer_class = StudentSerializer
    permission_classes = [IsStaffOrSuperUser]
    lookup_field = 'student_id'


class DisciplineViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Набор представлений для просмотра списка дисциплин.
    
    Доступ: Только для сотрудников и администраторов.
    
    Параметры URL:
        lookup_field: discipline_id (INTEGER)
    """
    queryset = Discipline.objects.all()
    serializer_class = DisciplineSerializer
    permission_classes = [IsStaffOrSuperUser]
    lookup_field = 'discipline_id'


class ResultTypeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Набор представлений для просмотра типов результатов оценивания 
    (например: "Зачтено", "5", "Не зачтено").
    
    Доступ: Только для сотрудников и администраторов.
    
    Параметры URL:
        lookup_field: result_id (INTEGER)
    """
    queryset = ResultType.objects.all()
    serializer_class = ResultTypeSerializer
    permission_classes = [IsStaffOrSuperUser]
    lookup_field = 'result_id'

class StudentResultViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Набор представлений для просмотра академической успеваемости студентов.
    
    Содержит информацию о студенте, дисциплине и полученной оценке.
    Поддерживает фильтрацию по студенту и дисциплине.
    
    Доступ: Только для сотрудников и администраторов.
    
    Параметры фильтрации (Query Params):
        - student: ID студента
        - discipline: ID дисциплины
    
    Пример запроса: /api/student-results/?student=123&discipline=45
    """
    queryset = StudentResult.objects.select_related(
        'student__group__speciality__faculty',
        'discipline',
        'result'
    ).all()
    serializer_class = StudentResultSerializer
    permission_classes = [IsStaffOrSuperUser]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['student', 'discipline']


class AttendanceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Набор представлений для просмотра данных о посещаемости занятий.
    
    Содержит информацию о студенте, дисциплине, ID занятия и времени отметки.
    Поддерживает фильтрацию по студенту, дисциплине и конкретному занятию.
    
    Доступ: Только для сотрудников и администраторов.
    
    Параметры фильтрации (Query Params):
        - student: ID студента
        - discipline: ID дисциплины
        - lesson_id: ID конкретного занятия
    
    Пример запроса: /api/attendance/?student=123&lesson_id=99
    """
    queryset = Attendance.objects.select_related(
        'student__group__speciality__faculty',
        'discipline'
    ).all()
    serializer_class = AttendanceSerializer
    permission_classes = [IsStaffOrSuperUser]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['student', 'discipline', 'lesson_id']