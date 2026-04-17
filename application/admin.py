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
