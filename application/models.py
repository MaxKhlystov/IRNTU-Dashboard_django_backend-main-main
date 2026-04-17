from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin

class AdministratorManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Электронная почта обязательна')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)


class Administrator(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True, verbose_name="Электронная почта")
    name = models.CharField(max_length=255, verbose_name="ФИО")
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    groups = models.ManyToManyField(
        'auth.Group',
        related_name='administrator_groups',  # Уникальное имя обратной связи
        blank=True,
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='administrator_permissions',  # Уникальное имя обратной связи
        blank=True,
    )

    objects = AdministratorManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']

    class Meta:
        verbose_name = "Администратор"
        verbose_name_plural = "Администраторы"

##################################################################################################
class Faculty(models.Model):
    faculty_id = models.IntegerField(primary_key=True, verbose_name="ID факультета")
    name = models.CharField(max_length=255, verbose_name="Название факультета")

    class Meta:
        managed = False
        db_table = 'faculty'
        verbose_name = "Факультет"
        verbose_name_plural = "Факультеты"

    def __str__(self):
        return self.name


class Speciality(models.Model):
    speciality_id = models.IntegerField(primary_key=True, verbose_name="ID специальности")
    name = models.CharField(max_length=255, verbose_name="Название специальности")
    faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE, verbose_name="Факультет")

    class Meta:
        managed = False
        db_table = 'speciality'
        verbose_name = "Специальность"
        verbose_name_plural = "Специальности"

    def __str__(self):
        return self.name


class StudentGroup(models.Model):
    group_id = models.AutoField(primary_key=True, verbose_name="ID группы")
    name = models.CharField(max_length=50, verbose_name="Название группы")
    speciality = models.ForeignKey(Speciality, on_delete=models.CASCADE, verbose_name="Специальность")

    class Meta:
        managed = False
        db_table = 'student_group'
        verbose_name = "Группа студентов"
        verbose_name_plural = "Группы студентов"

    def __str__(self):
        return self.name


class Student(models.Model):
    student_id = models.IntegerField(primary_key=True, verbose_name="ID студента")
    birthday = models.TextField(verbose_name="Дата рождения", blank=True, null=True)
    is_academic = models.BooleanField(default=False, verbose_name="В академическом отпуске")
    group = models.ForeignKey(StudentGroup, on_delete=models.CASCADE, verbose_name="Группа")

    class Meta:
        managed = False
        db_table = 'student'
        verbose_name = "Студент"
        verbose_name_plural = "Студенты"

    def __str__(self):
        return f"Студент {self.student_id}"


class Discipline(models.Model):
    discipline_id = models.IntegerField(primary_key=True, verbose_name="ID дисциплины")
    name = models.CharField(max_length=255, verbose_name="Название дисциплины")

    class Meta:
        managed = False
        db_table = 'discipline'
        verbose_name = "Дисциплина"
        verbose_name_plural = "Дисциплины"

    def __str__(self):
        return self.name


class ResultType(models.Model):
    result_id = models.IntegerField(primary_key=True, verbose_name="ID результата")
    result_value = models.CharField(max_length=50, verbose_name="Значение результата")

    class Meta:
        managed = False
        db_table = 'result_type'
        verbose_name = "Тип результата"
        verbose_name_plural = "Типы результатов"

    def __str__(self):
        return self.result_value

class StudentResult(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, verbose_name="Студент",primary_key=True)
    discipline = models.ForeignKey(Discipline, on_delete=models.CASCADE, verbose_name="Дисциплина")
    result = models.ForeignKey(ResultType, on_delete=models.CASCADE, verbose_name="Результат")

    class Meta:
        managed = False
        db_table = 'student_result'
        verbose_name = "Результат студента"
        verbose_name_plural = "Результаты студентов"
        unique_together = (('student', 'discipline'),)

    def __str__(self):
        return f"{self.student} - {self.discipline}: {self.result}"
    
class Attendance(models.Model):
    lesson_id = models.IntegerField(verbose_name="ID занятия",primary_key=True)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, verbose_name="Студент")
    created_at = models.DateTimeField(verbose_name="Дата создания")
    updated_at = models.DateTimeField(verbose_name="Дата обновления")
    user_id = models.IntegerField(verbose_name="ID пользователя")
    discipline = models.ForeignKey(Discipline, on_delete=models.CASCADE, verbose_name="Дисциплина")

    class Meta:
        managed = False
        db_table = 'attendance'
        verbose_name = "Посещаемость"
        verbose_name_plural = "Посещаемость"
        unique_together = (('lesson_id', 'student'),)

    def __str__(self):
        return f"{self.student} - {self.lesson_id} ({self.discipline})"