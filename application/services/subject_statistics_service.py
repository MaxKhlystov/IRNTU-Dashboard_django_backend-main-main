from collections import defaultdict
from datetime import datetime
from typing import Optional, List
from django.db.models import Count
from django.core.cache import cache
from application.models import Student, StudentResult, Attendance


class SubjectStatisticsService:

    @staticmethod
    def calculate_course(year):
        now = datetime.now()
        return now.year - year if now.month < 9 else now.year - year + 1

    @staticmethod
    def extract_year_from_group_name(name):
        try:
            y = int(name.split('-')[1][:2])
            current = datetime.now().year % 100
            return (2000 if y <= current else 1900) + y
        except:
            return None

    @staticmethod
    def normalize(v):
        if not v:
            return None
        v = v.strip()
        if v in ["2", "3", "4", "5"]:
            return int(v)
        if v == "Зачтено":
            return "зачет"
        if v == "Не зачтено":
            return "незачет"
        if v == "Н/Я":
            return "неявка"
        return None

    @classmethod
    def get_students_in_course(cls, course):
        students = Student.objects.select_related('group').filter(is_academic=False)
        res = []

        for s in students:
            if not s.group:
                continue
            year = cls.extract_year_from_group_name(s.group.name)
            if year and cls.calculate_course(year) == int(course):
                res.append(s.student_id)

        return res

    @classmethod
    def get_statistics(cls, course=None, subject=None, groups=None, sort_by='avg', limit=20):

        cache_key = f"stats:{course}:{subject}:{groups}:{sort_by}:{limit}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        qs = StudentResult.objects.select_related(
            'student__group', 'discipline', 'result'
        ).filter(student__is_academic=False)

        if groups:
            if isinstance(groups, str):
                groups = [g.strip() for g in groups.split(',') if g]

            qs = qs.filter(student__group__name__in=groups)

        if course:
            ids = cls.get_students_in_course(course)
            if not ids:
                return cls._empty()
            qs = qs.filter(student_id__in=ids)

        if subject:
            qs = qs.filter(discipline__name__icontains=subject)

        results = list(qs)

        numeric = []
        dist = {'2': 0, '3': 0, '4': 0, '5': 0}

        data = defaultdict(lambda: {
            "name": None,
            "grades": [],
            "students": set(),
            "debts": 0,
            "total": 0
        })

        all_students = set()
        disciplines = set()

        for r in results:
            val = r.result.result_value if r.result else None
            norm = cls.normalize(val)
            if norm is None:
                continue

            d_id = r.discipline_id
            s_id = r.student_id

            disciplines.add(d_id)
            all_students.add(s_id)

            d = data[d_id]
            d["name"] = r.discipline.name
            d["students"].add(s_id)
            d["total"] += 1

            if isinstance(norm, int):
                numeric.append(norm)
                dist[str(norm)] += 1
                d["grades"].append(norm)
                if norm == 2:
                    d["debts"] += 1
            elif norm in ["незачет", "неявка"]:
                d["debts"] += 1

        attendance_rows = Attendance.objects.filter(
            discipline_id__in=disciplines,
            student_id__in=all_students
        ).values('discipline_id', 'student_id').annotate(
            visits=Count('lesson_id')
        )

        att_map = defaultdict(list)
        for row in attendance_rows:
            att_map[row['discipline_id']].append(row['visits'])

        def calc_att(v):
            if not v:
                return 0
            m = max(v)
            if m == 0:
                return 0
            return round(sum((x/m)*100 for x in v)/len(v), 2)

        if numeric:
            stats = {
                "minGrade": min(numeric),
                "avgGrade": round(sum(numeric)/len(numeric), 2),
                "maxGrade": max(numeric)
            }
        else:
            stats = {"minGrade": None, "avgGrade": None, "maxGrade": None}

        subjects = []

        for d_id, d in data.items():
            grades = d["grades"]
            total = d["total"]

            avg = sum(grades)/len(grades) if grades else 0
            debt_ratio = d["debts"]/total if total else 0
            att = calc_att(att_map.get(d_id, []))

            activity = round((avg*0.5) + ((att/100*5)*0.3) + ((1-debt_ratio)*5*0.2), 2)

            subjects.append({
                "subject": d["name"],
                "avg": round(avg, 2),
                "max": max(grades) if grades else 0,
                "count": len(grades),
                "avgAttendance": att,
                "avgActivity": activity
            })

        key = {
            "avg": "avg",
            "max": "max",
            "count": "count",
            "activity": "avgActivity"
        }.get(sort_by, "avg")

        subjects.sort(key=lambda x: x[key], reverse=True)

        result = {
            "subjectStats": stats,
            "gradeDistributionBar": dist,
            "bestSubjects": subjects[:limit]
        }

        cache.set(cache_key, result, 300)

        return result

    @staticmethod
    def _empty():
        return {
            "subjectStats": {"minGrade": None, "avgGrade": None, "maxGrade": None},
            "gradeDistributionBar": {'2': 0, '3': 0, '4': 0, '5': 0},
            "bestSubjects": []
        }
