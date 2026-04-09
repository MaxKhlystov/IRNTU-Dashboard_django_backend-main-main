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


##################################################################################################
# class Academ(models.Model):
#     academ_id = models.AutoField(db_column='Academ_ID', primary_key=True, verbose_name="ID академотпуска")
#     student = models.ForeignKey('Student', models.DO_NOTHING, db_column='Student_ID', verbose_name="Студент")
#     previous_group = models.ForeignKey('Group', models.DO_NOTHING, db_column='Previous_Group', blank=True, null=True, verbose_name="Предыдущая группа")
#     relevant_group = models.ForeignKey('Group', models.DO_NOTHING, db_column='Relevant_Group', related_name='academ_relevant_group_set', blank=True, null=True, verbose_name="Текущая группа")
#     start_date = models.DateField(db_column='Start_date', verbose_name="Дата начала")
#     end_date = models.DateField(db_column='End_date', blank=True, null=True, verbose_name="Дата окончания")

#     class Meta:
#         managed = False
#         db_table = 'Academ'
#         verbose_name = "Академический отпуск"
#         verbose_name_plural = "Академические отпуска"

#     def __str__(self) -> str:
#         student = self.student
#         full_name = f"{student.name}"
#         return f"{full_name} ({self.start_date} - {self.end_date if self.end_date else 'настоящее время'})"
    
# class Attendance(models.Model):
#     att_id = models.AutoField(db_column='ATT_ID', primary_key=True, verbose_name="ID посещаемости")
#     nagruzka = models.ForeignKey('Nagruzka', models.DO_NOTHING, db_column='Nagruzka_ID', blank=True, null=True, verbose_name="Нагрузка")
#     student = models.ForeignKey('Student', models.DO_NOTHING, db_column='Student_ID', blank=True, null=True, verbose_name="Студент")
#     percent_of_attendance = models.FloatField(db_column='Percent_of_attendance', blank=True, null=True, verbose_name="Процент посещаемости")

#     class Meta:
#         managed = False
#         db_table = 'Attendance'
#         verbose_name = "Посещаемость"
#         verbose_name_plural = "Посещаемость"

#     def __str__(self) -> str:
#         return f"{self.student} - {self.percent_of_attendance}%" if self.student else f"Без студента - {self.percent_of_attendance}%"
    
# class CourseProjects(models.Model):
#     course_id = models.AutoField(db_column='Course_ID', primary_key=True, verbose_name="ID курсового проекта")
#     student = models.ForeignKey('Student', models.DO_NOTHING, db_column='Student_ID', blank=True, null=True, verbose_name="Студент")
#     hps = models.ForeignKey('HoursPerSemest', models.DO_NOTHING, db_column='HPS_ID', blank=True, null=True, verbose_name="Часы в семестре")
#     grade = models.IntegerField(db_column='Grade', blank=True, null=True, verbose_name="Оценка")

#     class Meta:
#         managed = False
#         db_table = 'Course_projects'
#         verbose_name = "Курсовой проект"
#         verbose_name_plural = "Курсовые проекты"

#     def __str__(self) -> str:
#         return f"{self.student} - Оценка: {self.grade if self.grade is not None else 'нет'}"
    
# class DebtAudit(models.Model):
#     audit_id = models.AutoField(db_column='Audit_ID', primary_key=True, verbose_name="ID аудита")
#     date = models.DateField(db_column='Date', verbose_name="Дата")
#     debt_event = models.CharField(db_column='Debt_Event', max_length=20, db_collation='Cyrillic_General_CI_AS', blank=True, null=True, verbose_name="Событие задолженности")
#     debt = models.ForeignKey('Debts', models.DO_NOTHING, db_column='Debt_ID', verbose_name="Задолженность")

#     class Meta:
#         managed = False
#         db_table = 'Debt_audit'
#         verbose_name = "Аудит задолженности"
#         verbose_name_plural = "Аудиты задолженностей"

#     def __str__(self) -> str:
#         return f"Аудит {self.audit_id} - {self.date}"
    
# class Debts(models.Model):
#     debt_id = models.AutoField(db_column='Debt_ID', primary_key=True, verbose_name="ID задолженности")
#     hps = models.ForeignKey('HoursPerSemest', models.DO_NOTHING, db_column='HPS_ID', verbose_name="Часы в семестре")
#     student = models.ForeignKey('Student', models.DO_NOTHING, db_column='Student_ID', verbose_name="Студент")

#     class Meta:
#         managed = False
#         db_table = 'Debts'
#         verbose_name = "Задолженность"
#         verbose_name_plural = "Задолженности"

#     def __str__(self) -> str:
#         return f"Задолженность {self.debt_id}"
    
# class Diploma(models.Model):
#     diploma_id = models.AutoField(db_column='Diploma_ID', primary_key=True, verbose_name="ID диплома")
#     student = models.ForeignKey('Student', models.DO_NOTHING, db_column='Student_ID', blank=True, null=True, verbose_name="Студент")
#     teacher = models.ForeignKey('Teachers', models.DO_NOTHING, db_column='Teacher_ID', blank=True, null=True, verbose_name="Преподаватель")
#     plan = models.ForeignKey('EducationPlan', models.DO_NOTHING, db_column='Plan_ID', blank=True, null=True, verbose_name="Учебный план")
#     grade = models.IntegerField(db_column='Grade', blank=True, null=True, verbose_name="Оценка")

#     class Meta:
#         managed = False
#         db_table = 'Diploma'
#         verbose_name = "Диплом"
#         verbose_name_plural = "Дипломы"
    
#     def __str__(self):
#         return f"Диплом {self.diploma_id}"
    
# class Disciples(models.Model):
#     disciple_id = models.AutoField(db_column='Disciple_ID', primary_key=True, verbose_name="ID дисциплины")
#     disciple_name = models.CharField(
#         db_column='Disciple_name', max_length=255, db_collation='Cyrillic_General_CI_AS',
#         blank=True, null=True, verbose_name="Название дисциплины"
#     )

#     class Meta:
#         managed = False
#         db_table = 'Disciples'
#         verbose_name = "Дисциплина"
#         verbose_name_plural = "Дисциплины"

#     def __str__(self) -> str:
#         return self.disciple_name if self.disciple_name else "Без названия"
    
# class EducationPlan(models.Model):
#     plan_id = models.AutoField(db_column='Plan_ID', primary_key=True, verbose_name="ID плана")
#     code = models.ForeignKey(
#         'Specialty', models.DO_NOTHING, db_column='Code', blank=True, null=True, verbose_name="Специальность"
#     )
#     year_of_conclude = models.IntegerField(db_column='Year_of_conclude', blank=True, null=True, verbose_name="Год утверждения")

#     class Meta:
#         managed = False
#         db_table = 'Education_plan'
#         verbose_name = "Учебный план"
#         verbose_name_plural = "Учебные планы"

#     def __str__(self) -> str:
#         return f"План {self.code} - {self.year_of_conclude}" if self.code else f"План без кода - {self.year_of_conclude}"
    
# class FormControl(models.Model):
#     fc_id = models.AutoField(db_column='FC_ID', primary_key=True, verbose_name="ID формы контроля")
#     hps = models.ForeignKey(
#         'HoursPerSemest', models.DO_NOTHING, db_column='HPS_ID', blank=True, null=True, verbose_name="Часы по семестру"
#     )
#     form = models.CharField(
#         db_column='Form', max_length=255, db_collation='Cyrillic_General_CI_AS',
#         blank=True, null=True, verbose_name="Форма контроля"
#     )

#     class Meta:
#         managed = False
#         db_table = 'Form_Control'
#         verbose_name = "Форма контроля"
#         verbose_name_plural = "Формы контроля"

#     def __str__(self) -> str:
#         return self.form if self.form else "Не указана"
    
# class Grades(models.Model):
#     grade_id = models.AutoField(db_column='Grade_ID', primary_key=True, verbose_name="ID оценки")
#     student = models.ForeignKey('Student', models.DO_NOTHING, db_column='Student_ID', blank=True, null=True, verbose_name="Студент")
#     fc = models.ForeignKey(FormControl, models.DO_NOTHING, db_column='FC_ID', blank=True, null=True, verbose_name="Форма контроля")
#     grade = models.CharField(db_column='Grade', max_length=20, db_collation='Cyrillic_General_CI_AS', blank=True, null=True, verbose_name="Оценка")

#     class Meta:
#         managed = False
#         db_table = 'Grades'
#         verbose_name = "Оценка"
#         verbose_name_plural = "Оценки"

#     def __str__(self) -> str:
#         return f"{self.student} - {self.grade}" if self.student else f"Без студента - {self.grade}"
    
# class Group(models.Model):
#     group_id = models.AutoField(db_column='Group_ID', primary_key=True, verbose_name="ID группы")
#     title = models.CharField(db_column='Title', max_length=255, db_collation='Cyrillic_General_CI_AS', blank=True, null=True, verbose_name="Название группы")
#     plan = models.ForeignKey(EducationPlan, models.DO_NOTHING, db_column='Plan_ID', blank=True, null=True, verbose_name="Учебный план")

#     class Meta:
#         managed = False
#         db_table = 'Group'
#         verbose_name = "Группа"
#         verbose_name_plural = "Группы"

#     def __str__(self) -> str:
#         return self.title if self.title else "Без названия"
    
# class HoursPerSemest(models.Model):
#     hps_id = models.AutoField(db_column='HPS_ID', primary_key=True, verbose_name="ID часов в семестр")
#     plan = models.ForeignKey(EducationPlan, models.DO_NOTHING, db_column='Plan_ID', blank=True, null=True, verbose_name="Учебный план")
#     disciple = models.ForeignKey(Disciples, models.DO_NOTHING, db_column='Disciple_ID', blank=True, null=True, verbose_name="Дисциплина")
#     hours = models.IntegerField(db_column='Hours', blank=True, null=True, verbose_name="Количество часов")
#     semester = models.IntegerField(db_column='Semester', blank=True, null=True, verbose_name="Семестр")
#     start_date = models.DateField(db_column='Start_date', blank=True, null=True, verbose_name="Дата начала")
#     end_date = models.DateField(db_column='End_date', blank=True, null=True, verbose_name="Дата окончания")

#     class Meta:
#         managed = False
#         db_table = 'Hours_per_semest'
#         verbose_name = "Часы в семестр"
#         verbose_name_plural = "Часы в семестр"

#     def __str__(self) -> str:
#         return f"{self.disciple} - {self.semester} семестр ({self.hours} ч.)" if self.disciple else "Без дисциплины"
    
# class Nagruzka(models.Model):
#     nagruzka_id = models.AutoField(db_column='Nagruzka_ID', primary_key=True, verbose_name="ID нагрузки")
#     teacher = models.ForeignKey('Teachers', models.DO_NOTHING, db_column='Teacher_ID', blank=True, null=True, verbose_name="Преподаватель")
#     group = models.ForeignKey(Group, models.DO_NOTHING, db_column='Group_ID', blank=True, null=True, verbose_name="Группа")
#     fc = models.ForeignKey(FormControl, models.DO_NOTHING, db_column='FC_ID', blank=True, null=True, verbose_name="Форма контроля")

#     class Meta:
#         managed = False
#         db_table = 'Nagruzka'
#         verbose_name = "Нагрузка"
#         verbose_name_plural = "Нагрузки"

#     def __str__(self):
#         return f"{self.teacher} - {self.group}" if self.teacher and self.group else "Нагрузка без данных"
    
# class Practise(models.Model):
#     practise_id = models.AutoField(db_column='Practise_ID', primary_key=True, verbose_name="ID практики")
#     student = models.ForeignKey('Student', models.DO_NOTHING, db_column='Student_ID', blank=True, null=True, verbose_name="Студент")
#     plan = models.ForeignKey(EducationPlan, models.DO_NOTHING, db_column='Plan_ID', blank=True, null=True, verbose_name="Учебный план")
#     type = models.ForeignKey('PractiseType', models.DO_NOTHING, db_column='Type_ID', blank=True, null=True, verbose_name="Тип практики")
#     grade = models.IntegerField(db_column='Grade', blank=True, null=True, verbose_name="Оценка")

#     class Meta:
#         managed = False
#         db_table = 'Practise'
#         verbose_name = "Практика"
#         verbose_name_plural = "Практики"

#     def __str__(self):
#         return f"{self.student} - {self.type} ({self.grade if self.grade is not None else 'без оценки'})"
    
# class PractiseType(models.Model):
#     type_id = models.AutoField(db_column='Type_ID', primary_key=True, verbose_name="ID типа практики")
#     title = models.CharField(db_column='Title', max_length=255, db_collation='Cyrillic_General_CI_AS', blank=True, null=True, verbose_name="Название типа")

#     class Meta:
#         managed = False
#         db_table = 'Practise_type'
#         verbose_name = "Тип практики"
#         verbose_name_plural = "Типы практик"

#     def __str__(self):
#         return self.title if self.title else "Без названия"
    
# class Rating(models.Model):
#     rating_id = models.AutoField(db_column='Rating_ID', primary_key=True, verbose_name="ID рейтинга")
#     type = models.ForeignKey('RatingType', models.DO_NOTHING, db_column='Type_ID', blank=True, null=True, verbose_name="Тип рейтинга")
#     event = models.CharField(db_column='Event', max_length=255, db_collation='Cyrillic_General_CI_AS', blank=True, null=True, verbose_name="Событие")
#     score = models.IntegerField(db_column='Score', blank=True, null=True, verbose_name="Баллы")

#     class Meta:
#         managed = False
#         db_table = 'Rating'
#         verbose_name = "Рейтинг"
#         verbose_name_plural = "Рейтинги"

#     def __str__(self):
#         return f"{self.event} - {self.score if self.score is not None else 'без баллов'}"
    
# class RatingType(models.Model):
#     type_id = models.AutoField(db_column='Type_ID', primary_key=True, verbose_name="ID типа рейтинга")
#     title = models.CharField(db_column='Title', max_length=255, db_collation='Cyrillic_General_CI_AS', blank=True, null=True, verbose_name="Название")

#     class Meta:
#         managed = False
#         db_table = 'Rating_type'
#         verbose_name = "Тип рейтинга"
#         verbose_name_plural = "Типы рейтинга"

#     def __str__(self):
#         return self.title if self.title else "Без названия"
    
# class Specialty(models.Model):
#     code = models.CharField(db_column='Code', primary_key=True, max_length=255, db_collation='Cyrillic_General_CI_AS', verbose_name="Код")
#     title = models.CharField(db_column='Title', max_length=255, db_collation='Cyrillic_General_CI_AS', blank=True, null=True, verbose_name="Название")

#     class Meta:
#         managed = False
#         db_table = 'Specialty'
#         verbose_name = "Специальность"
#         verbose_name_plural = "Специальности"

#     def __str__(self):
#         return f"{self.code} - {self.title}" if self.title else self.code
    
# class Student(models.Model):
#     student_id = models.AutoField(db_column='Student_ID', primary_key=True, verbose_name="ID студента")
#     group = models.ForeignKey('Group', models.DO_NOTHING, db_column='Group_ID', blank=True, null=True, verbose_name="Группа")
#     rating = models.ForeignKey('Rating', models.DO_NOTHING, db_column='Rating_ID', blank=True, null=True, verbose_name="Рейтинг")
#     name = models.CharField(db_column='Name', max_length=255, db_collation='Cyrillic_General_CI_AS', blank=True, null=True, verbose_name="ФИО")
#     birth_date = models.DateField(db_column='Birth_date', blank=True, null=True, verbose_name="Дата рождения")
#     sex = models.CharField(db_column='Sex', max_length=255, db_collation='Cyrillic_General_CI_AS', blank=True, null=True, verbose_name="Пол")
#     entry_score = models.IntegerField(db_column='Entry_score', blank=True, null=True, verbose_name="Баллы при поступлении")
#     school = models.CharField(db_column='School', max_length=255, db_collation='Cyrillic_General_CI_AS', blank=True, null=True, verbose_name="Школа")
#     debt = models.BooleanField(db_column='Debt', blank=True, null=True, verbose_name="Долг по предметам")
#     middle_value_of_sertificate = models.CharField(db_column='Middle_value_of_sertificate', max_length=255, db_collation='Cyrillic_General_CI_AS', blank=True, null=True, verbose_name="Средний балл аттестата")

#     class Meta:
#         managed = False
#         db_table = 'Student'
#         verbose_name = "Студент"
#         verbose_name_plural = "Студенты"

#     def __str__(self):
#         return self.name if self.name else "Неизвестный студент"
    
# class Teachers(models.Model):
#     teacher_id = models.AutoField(db_column='Teacher_ID', primary_key=True, verbose_name="ID преподавателя")
#     teacher_name = models.CharField(db_column='Teacher_name', max_length=255, db_collation='Cyrillic_General_CI_AS', blank=True, null=True, verbose_name="ФИО преподавателя")

#     class Meta:
#         managed = False
#         db_table = 'Teachers'
#         verbose_name = "Преподаватель"
#         verbose_name_plural = "Преподаватели"

#     def __str__(self):
#         return self.teacher_name if self.teacher_name else "Неизвестный преподаватель"
