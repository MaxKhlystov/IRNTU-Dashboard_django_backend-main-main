# from django.contrib import admin

# # from .models import (
# #     Teacher, Student, Group, Disciple, Attendance, Course_project, Diploma,
# #     Education_plan, Form_control, Grade, Hours_per_semestr, Complexity, Practise,
# #     Practise_type, Rating, Rating_type, Speciality, Administrator
# # )
# from .models import Academ, Attendance, CourseProjects, DebtAudit, Debts, Diploma, Disciples, EducationPlan, FormControl, Grades, Group, HoursPerSemest, Nagruzka, Practise, PractiseType, Rating, RatingType, Specialty, Student, Teachers
# from .models import Administrator

# @admin.register(Administrator)
# class AdministratorAdmin(admin.ModelAdmin):
#     list_display = ['name', 'email', 'is_active', 'is_staff', 'is_superuser']
#     search_fields = ['name']
# ####################################################################################################################
# @admin.register(Academ)
# class AcademAdmin(admin.ModelAdmin):
#     list_display = ['student', 'previous_group', 'relevant_group', 'start_date', 'end_date']
#     list_filter = ['previous_group', 'relevant_group', 'start_date', 'end_date']
#     search_fields = ['student__name', 'start_date', 'end_date']
    
# @admin.register(Attendance)
# class AttendanceAdmin(admin.ModelAdmin):
#     list_display = ['student', 'nagruzka', 'percent_of_attendance']
#     list_filter = ['nagruzka', 'student']
#     search_fields = ['student__name', 'percent_of_attendance']

# @admin.register(CourseProjects)
# class CourseProjectsAdmin(admin.ModelAdmin):
#     list_display = ['student', 'hps', 'grade']
#     list_filter = ['student', 'hps', 'grade']
#     search_fields = ['student__name', 'hps__hours', 'grade']

# @admin.register(DebtAudit)
# class DebtAuditAdmin(admin.ModelAdmin):
#     list_display = ['date', 'debt_event', 'debt']
#     list_filter = ['date', 'debt_event', 'debt']
#     search_fields = ['debt_event', 'debt__name', 'date']

# @admin.register(Debts)
# class DebtsAdmin(admin.ModelAdmin):
#     list_display = ['student', 'hps']
#     list_filter = ['student', 'hps']
#     search_fields = ['student__name', 'hps__hours']

# @admin.register(Diploma)
# class DiplomaAdmin(admin.ModelAdmin):
#     list_display = ['student', 'teacher', 'plan', 'grade']
#     list_filter = ['student', 'teacher', 'plan', 'grade']
#     search_fields = ['student__name', 'teacher__last_name', 'teacher__first_name', 'plan__name', 'grade']

# @admin.register(Disciples)
# class DisciplesAdmin(admin.ModelAdmin):
#     list_display = ['disciple_name']
#     search_fields = ['disciple_name']

# @admin.register(EducationPlan)
# class EducationPlanAdmin(admin.ModelAdmin):
#     list_display = ['code', 'year_of_conclude']
#     list_filter = ['code', 'year_of_conclude']
#     search_fields = ['code__name', 'year_of_conclude']

# @admin.register(FormControl)
# class FormControlAdmin(admin.ModelAdmin):
#     list_display = ['hps', 'form']
#     list_filter = ['hps', 'form']
#     search_fields = ['hps__hours', 'form']

# @admin.register(Grades)
# class GradesAdmin(admin.ModelAdmin):
#     list_display = ['student', 'fc', 'grade']
#     list_filter = ['student', 'fc', 'grade']
#     search_fields = ['student__name', 'fc__form', 'grade']

# @admin.register(Group)
# class GroupAdmin(admin.ModelAdmin):
#     list_display = ['title', 'plan']
#     list_filter = ['plan']
#     search_fields = ['title', 'plan__code__name']

# @admin.register(HoursPerSemest)
# class HoursPerSemestAdmin(admin.ModelAdmin):
#     list_display = ['disciple', 'semester', 'hours', 'start_date', 'end_date']
#     list_filter = ['disciple', 'semester', 'start_date', 'end_date']
#     search_fields = ['disciple__disciple_name', 'semester', 'hours']

# @admin.register(Nagruzka)
# class NagruzkaAdmin(admin.ModelAdmin):
#     list_display = ['teacher', 'group', 'fc']
#     list_filter = ['teacher', 'group', 'fc']
#     search_fields = ['teacher__last_name', 'group__title', 'fc__form']

# @admin.register(Practise)
# class PractiseAdmin(admin.ModelAdmin):
#     list_display = ['student', 'type', 'grade']
#     list_filter = ['student', 'type', 'grade']
#     search_fields = ['student__name', 'type__title', 'grade']

# @admin.register(PractiseType)
# class PractiseTypeAdmin(admin.ModelAdmin):
#     list_display = ['title']
#     search_fields = ['title']

# @admin.register(Rating)
# class RatingAdmin(admin.ModelAdmin):
#     list_display = ['type', 'event', 'score']
#     list_filter = ['type', 'score']
#     search_fields = ['event', 'type__title', 'score']

# @admin.register(RatingType)
# class RatingTypeAdmin(admin.ModelAdmin):
#     list_display = ['title']
#     search_fields = ['title']

# @admin.register(Specialty)
# class SpecialtyAdmin(admin.ModelAdmin):
#     list_display = ['code', 'title']
#     search_fields = ['code', 'title']

# @admin.register(Student)
# class StudentAdmin(admin.ModelAdmin):
#     list_display = ['name', 'group', 'rating', 'birth_date', 'sex', 'entry_score', 'school', 'debt', 'middle_value_of_sertificate']
#     list_filter = ['group', 'rating', 'sex', 'debt']
#     search_fields = ['name', 'group__title', 'rating__event', 'school']

# @admin.register(Teachers)
# class TeachersAdmin(admin.ModelAdmin):
#     list_display = ['teacher_name']
#     search_fields = ['teacher_name']
# ####################################################################################################################
from django.contrib import admin
from .models import (
    Administrator, Faculty, Speciality, StudentGroup, 
    Student, Discipline, ResultType, StudentResult, Attendance
)

@admin.register(Administrator)
class AdministratorAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'is_active', 'is_staff', 'is_superuser']
    search_fields = ['name', 'email']
    list_filter = ['is_active', 'is_staff', 'is_superuser']

@admin.register(Faculty)
class FacultyAdmin(admin.ModelAdmin):
    list_display = ['faculty_id', 'name']
    search_fields = ['name']
    list_filter = ['faculty_id']

@admin.register(Speciality)
class SpecialityAdmin(admin.ModelAdmin):
    list_display = ['speciality_id', 'name', 'faculty']
    search_fields = ['name', 'faculty__name']
    list_filter = ['faculty']

@admin.register(StudentGroup)
class StudentGroupAdmin(admin.ModelAdmin):
    list_display = ['group_id', 'name', 'speciality']
    search_fields = ['name', 'speciality__name']
    list_filter = ['speciality']

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['student_id', 'birthday', 'is_academic', 'group']
    search_fields = ['student_id', 'group__name']
    list_filter = ['is_academic', 'group']

@admin.register(Discipline)
class DisciplineAdmin(admin.ModelAdmin):
    list_display = ['discipline_id', 'name']
    search_fields = ['name']
    list_filter = ['discipline_id']

@admin.register(ResultType)
class ResultTypeAdmin(admin.ModelAdmin):
    list_display = ['result_id', 'result_value']
    search_fields = ['result_value']
    list_filter = ['result_id']

@admin.register(StudentResult)
class StudentResultAdmin(admin.ModelAdmin):
    list_display = ['student', 'discipline', 'result']
    search_fields = ['student__student_id', 'discipline__name', 'result__result_value']
    list_filter = ['discipline', 'result']

@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ['student', 'lesson_id', 'discipline', 'user_id', 'created_at','updated_at']
    search_fields = ['student__student_id', 'discipline__name', 'lesson_id']
    list_filter = ['discipline', 'created_at']
