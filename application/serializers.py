from rest_framework import serializers
from application.models import Administrator
from application.models import (
    Faculty, Speciality, StudentGroup, Student, 
    Discipline, ResultType, StudentResult, Attendance
)

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

class RegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Administrator
        fields = ['email', 'name', 'password']
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        email = validated_data.pop('email')
        password = validated_data.pop('password')
        user = Administrator.objects.create_user(email=email, password=password, **validated_data)
        return user


class FacultySerializer(serializers.ModelSerializer):
    class Meta:
        model = Faculty
        fields = ['faculty_id', 'name']

class SpecialitySerializer(serializers.ModelSerializer):
    faculty_name = serializers.CharField(source='faculty.name', read_only=True)
    
    class Meta:
        model = Speciality
        fields = ['speciality_id', 'name', 'faculty', 'faculty_name']

class StudentGroupSerializer(serializers.ModelSerializer):
    speciality_name = serializers.CharField(source='speciality.name', read_only=True)
    faculty_name = serializers.CharField(source='speciality.faculty.name', read_only=True)
    
    class Meta:
        model = StudentGroup
        fields = ['group_id', 'name', 'speciality', 'speciality_name', 'faculty_name']

class StudentSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source='group.name', read_only=True)
    speciality_name = serializers.CharField(source='group.speciality.name', read_only=True)
    faculty_name = serializers.CharField(source='group.speciality.faculty.name', read_only=True)
    
    class Meta:
        model = Student
        fields = [
            'student_id', 'birthday', 'is_academic', 'group', 
            'group_name', 'speciality_name', 'faculty_name'
        ]

class DisciplineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Discipline
        fields = ['discipline_id', 'name']

class ResultTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResultType
        fields = ['result_id', 'result_value']

class StudentResultSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.student_id', read_only=True)
    discipline_name = serializers.CharField(source='discipline.name', read_only=True)
    result_value = serializers.CharField(source='result.result_value', read_only=True)
    
    class Meta:
        model = StudentResult
        fields = [
            'student', 'student_name', 'discipline', 'discipline_name', 
            'result', 'result_value'
        ]

class AttendanceSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.student_id', read_only=True)
    discipline_name = serializers.CharField(source='discipline.name', read_only=True)
    
    class Meta:
        model = Attendance
        fields = [
            'lesson_id', 'student', 'student_name', 'created_at', 
            'updated_at', 'user_id', 'discipline', 'discipline_name'
        ]