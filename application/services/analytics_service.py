import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from django.db.models import Count
from application.models import Student, Attendance, StudentResult

def calculate_attendance_percentage():
    """
    Рассчитывает относительный процент посещаемости для каждого студента.
    
    Логика расчета:
    Посещаемость студента нормируется относительно самого активного студента 
    в его учебной группе по формуле:
        (Количество посещений студента / Макс. количество посещений в группе) * 100
    
    Это позволяет избежать зависимости от общего количества пар, которого может нет в базе
    
    Процесс:
    1. Агрегация количества посещений (lesson_id) для каждого студента из таблицы Attendance.
    2. Получение информации о принадлежности студентов к группам.
    3. Объединение данных и группировка по названиям групп.
    4. Вычисление максимума посещений внутри каждой группы.
    5. Расчет процента с защитой от деления на ноль.
    
    Returns:
        pd.DataFrame: Датафрейм с колонками:
            - 'student_id' (int): ID студента.
            - 'attendance_percent' (float): Процент посещаемости (0.0 - 100.0).
            Возвращает пустой DataFrame с заданными колонками, если данных нет.
    """
    # 1. Считаем количество посещений для каждого студента
    attendance_data = Attendance.objects.values('student_id').annotate(
        visits=Count('lesson_id')
    )
    
    if not attendance_data:
        return pd.DataFrame(columns=['student_id', 'attendance_percent'])

    df_attendance = pd.DataFrame(list(attendance_data))
    
    if 'student_id' in df_attendance.columns:
        pass 
    elif 'student' in df_attendance.columns:
        df_attendance.rename(columns={'student': 'student_id'}, inplace=True)
        
    if 'visits' in df_attendance.columns:
        df_attendance.rename(columns={'visits': 'attendance_count'}, inplace=True)
    
    # 2. Получаем информацию о группах студентов
    students_data = Student.objects.select_related('group').values(
        'student_id', 
        'group__name'
    )
    
    if not students_data:
        return pd.DataFrame(columns=['student_id', 'attendance_percent'])

    df_students = pd.DataFrame(list(students_data))
    df_students.rename(columns={
        'student_id': 'student_id', 
        'group__name': 'group'
    }, inplace=True)
    
    # 3. Объединяем посещаемость и группы
    df_merged = pd.merge(df_attendance, df_students, on='student_id', how='left')
    
    if df_merged.empty:
        return pd.DataFrame(columns=['student_id', 'attendance_percent'])

    # 4. Находим максимум посещений в каждой группе
    df_merged['group'] = df_merged['group'].fillna('Unknown_Group')
    
    group_max = df_merged.groupby('group')['attendance_count'].transform('max')
    
    # 5. Считаем процент (защита от деления на 0)
    df_merged['attendance_percent'] = np.where(
        group_max > 0, 
        (df_merged['attendance_count'] / group_max) * 100, 
        0.0
    )
    
    return df_merged[['student_id', 'attendance_percent']]

def calculate_avg_grades():
    """
    Рассчитывает средний балл успеваемости для каждого студента.
    
    Особенности обработки данных:
    - Извлекает все оценки из таблицы StudentResult вместе с их текстовым значением.
    - Безопасно преобразует строковые оценки ('5', '4', 'Зачтено', 'Н/Я') в числа.
    - Некорректные для среднего балла значения (например, "Зачтено") игнорируются (превращаются в NaN).
    - Исключает студентов, у которых нет ни одной числовой оценки.
    
    Process:
    1. Выборка данных через ORM с связанным полем result_value.
    2. Преобразование QuerySet в Pandas DataFrame.
    3. Применение функции to_numeric_safe для конвертации строк в float.
    4. Группировка по student_id и вычисление среднего арифметического (mean).
    
    Returns:
        pd.DataFrame: Датафрейм с колонками:
            - 'student_id' (int): ID студента.
            - 'avg_grade' (float): Средний балл.
            Возвращает пустой DataFrame, если данных нет или все оценки нечисловые.
    """
    # Получаем все записи результатов вместе со значением результата
    results_data = StudentResult.objects.select_related('result').values(
        'student_id',
        'result__result_value'
    )
    
    if not results_data:
        return pd.DataFrame(columns=['student_id', 'avg_grade'])

    df = pd.DataFrame(list(results_data))
    
    if df.empty:
        return pd.DataFrame(columns=['student_id', 'avg_grade'])

    df.rename(columns={'result__result_value': 'grade_str'}, inplace=True)

    def to_numeric_safe(val):
        if val is None:
            return np.nan
        try:
            return float(val)
        except (ValueError, TypeError):
            return np.nan

    # Применяем преобразование
    df['avg_grade'] = df['grade_str'].apply(to_numeric_safe)

    # Группировка по студенту и расчет среднего
    grades_stats = df.groupby('student_id').agg(
        avg_grade=('avg_grade', 'mean')
    ).reset_index()

    # Удаляем студентов, у которых не осталось ни одной числовой оценки
    grades_stats = grades_stats.dropna(subset=['avg_grade'])

    return grades_stats[['student_id', 'avg_grade']]

def run_analytics_pipeline():
    """
    Основной пайплайн аналитики студентов: сбор данных, кластеризация и формирование отчета.
    
    Выполняет полный цикл обработки данных для дашборда аналитики:
    1. Загружает посещаемость и оценки из БД через вспомогательные функции.
    2. Добавляет информацию о группе, специальности и факультете.
    3. Очищает данные, заполняет пропуски, приводит типы.
    4. Применяет алгоритм KMeans для сегментации студентов на группы 
       по признакам "Средний балл" и "Посещаемость". Количество кластеров фиксируется (k=3) 
       с адаптацией под малое количество данных.
    5. Считает средние показатели по учебным группам.
    6. Формирует JSON-совместимую структуру данных для фронтенда.
    
    Алгоритм кластеризации:
    - Используется StandardScaler для нормализации признаков (приведение к единому масштабу).
    - KMeans с фиксированным random_state для воспроизводимости результатов.
    - Обработка случаев, когда студентов меньше, чем предполагаемых кластеров.
    
    Returns:
        dict: Словарь со структурой:
            {
                "students": [
                    {
                        "student_id": int,
                        "group": str,
                        "speciality": str,
                        "faculty": str,
                        "avg_grade": float,
                        "attendance_percent": float,
                        "cluster": int
                    },
                    ...
                ],
                "group_stats": {
                    "Название группы": {
                        "avg_grade": float,
                        "attendance_percent": float
                    },
                    ...
                },
                "total_students": int,
                "clusters_count": int
            }
            
        В случае ошибки или отсутствия данных возвращает словарь с ключом "error".
    """
    # 1. Получаем данные
    df_attendance = calculate_attendance_percentage()
    df_grades = calculate_avg_grades()
    
    if df_attendance.empty and df_grades.empty:
        return {"error": "No data found in database", "students": [], "group_stats": {}}

    # 2. Объединяем данные
    # Используем outer join, чтобы не потерять студентов, у которых есть только оценки или только посещаемость
    data = pd.merge(df_grades, df_attendance, on='student_id', how='outer').fillna(0)
    
    if data.empty:
        return {"error": "No merged data", "students": [], "group_stats": {}}

    # 3. Добавляем информацию о студенте (Имя, Группа, Специальность, Факультет)
    students_info = Student.objects.select_related(
        'group', 
        'group__speciality', 
        'group__speciality__faculty'
    ).values(
        'student_id', 
        'group__name', 
        'group__speciality__name', 
        'group__speciality__faculty__name'
    )
    
    if not students_info:
        df_info = pd.DataFrame(columns=['student_id', 'group', 'speciality', 'faculty'])
    else:
        df_info = pd.DataFrame(list(students_info)).rename(columns={
            'student_id': 'student_id',
            'group__name': 'group',
            'group__speciality__name': 'speciality',
            'group__speciality__faculty__name': 'faculty'
        })
    
    data = pd.merge(data, df_info, on='student_id', how='left')

    data['group'] = data['group'].fillna('Неизвестная группа')
    data['speciality'] = data['speciality'].fillna('Неизвестная специальность')
    data['faculty'] = data['faculty'].fillna('Неизвестный факультет')

    # 4. Подготовка к кластеризации
    features_cols = ['avg_grade', 'attendance_percent']
    for col in features_cols:
        if col not in data.columns:
            data[col] = 0.0
        data[col] = pd.to_numeric(data[col], errors='coerce').fillna(0.0)

    features = data[features_cols].values
    
    if len(features) < 2:
        # Недостаточно данных для кластеризации
        data['cluster'] = 0
    else:
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(features)
        
        # Кластеризация
        best_k = 3 
        # Защита от случая, когда студентов меньше чем кластеров
        actual_k = min(best_k, len(data))
        if actual_k < 1: actual_k = 1
        
        kmeans = KMeans(n_clusters=actual_k, random_state=42, n_init=10)
        data['cluster'] = kmeans.fit_predict(X_scaled)
    
    # Формирование статистики по группам
    if not data.empty:
        group_stats_df = data.groupby('group')[['avg_grade', 'attendance_percent']].mean()
        group_stats = group_stats_df.to_dict('index')
        for g, stats in group_stats.items():
            group_stats[g] = {k: round(v, 2) for k, v in stats.items()}
    else:
        group_stats = {}
    
    # Подготовка ответа для фронтенда
    results = []
    cols_to_export = ['student_id', 'group', 'speciality', 'faculty', 'avg_grade', 'attendance_percent', 'cluster']

    for col in cols_to_export:
        if col not in data.columns:
            data[col] = None if col in ['speciality', 'faculty'] else 0.0

    for _, row in data.iterrows():
        results.append({
            "student_id": int(row['student_id']) if pd.notna(row['student_id']) else 0,
            "group": str(row['group']),
            "speciality": str(row['speciality']),
            "faculty": str(row['faculty']),
            "avg_grade": round(float(row['avg_grade']), 2),
            "attendance_percent": round(float(row['attendance_percent']), 2),
            "cluster": int(row['cluster'])
        })
        
    return {
        "students": results,
        "group_stats": group_stats,
        "total_students": len(data),
        "clusters_count": len(data['cluster'].unique()) if not data.empty else 0
    }