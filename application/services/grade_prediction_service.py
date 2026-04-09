import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from datetime import datetime
import numpy as np
import pandas as pd
import re
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from django.db.models import Avg, Count, FloatField
from django.db.models.functions import Cast
import os
import json
from django.conf import settings
from application.models import Student, StudentResult, Attendance, StudentGroup, Speciality, Faculty
from application.services.student_rating_service import StudentRatingService

class StudentDataset(Dataset):
    """
    Кастомный набор данных PyTorch для загрузки признаков студентов и их оценок.
    
    Преобразует numpy-массивы в тензоры PyTorch с плавающей точкой.
    Используется в DataLoader для пакетной обработки данных во время обучения.
    
    Attributes:
        X (torch.FloatTensor): Тензор признаков (features).
        y (torch.FloatTensor): Тензор целевых значений (оценок), размерность (N, 1).
    """
    def __init__(self, X, y):
        self.X = torch.FloatTensor(X)
        self.y = torch.FloatTensor(y).unsqueeze(1)
    
    def __len__(self):
        return len(self.X)
    
    def __getitem__(self, idx):
        return self.X[idx], self.y[idx]

class GradeRegressor(nn.Module):
    """
    Нейронная сеть для регрессии (предсказания средней оценки студента).
    
    Архитектура:
    - Входной слой: Принимает вектор признаков (размер зависит от количества фич).
    - Скрытые слои: 3 полносвязных слоя (32 -> 16 -> 8 нейронов).
    - Активации: ReLU после каждого скрытого слоя.
    - Регуляризация: Dropout (0.3) после первых двух скрытых слоев для борьбы с переобучением.
    - Выходной слой: 1 нейрон (предсказанная оценка).
    
    Функция потерь: MSE (Mean Squared Error).
    Оптимизатор: Adam.
    """
    def __init__(self, input_size):
        super().__init__()
        self.model = nn.Sequential(
            nn.Linear(input_size, 32),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(16, 8),
            nn.ReLU(),
            nn.Linear(8, 1)
        )
    
    def forward(self, x):
        return self.model(x)

def prepare_data_from_db(faculty_name: str, group_base: str, target_course: int):
    """
    Собирает и подготавливает данные из БД для обучения модели.
    
    Логика подготовки:
    1. Фильтрация: Выбор студентов указанного факультета и базовой группы (напр., "ИСТб").
    2. Обработка оценок: 
       - Нормализация строковых оценок ("Зачтено"->5.0, "Не зачтено"->2.0).
       - Расчет статистик: среднее, стд, мин, макс, распределение по категориям (отл/хор/удовл).
    3. Расчет посещаемости (Относительная метрика):
       - Для каждой дисциплины находится студент с макс. количеством посещений (эталон).
       - Посещаемость каждого студента нормируется относительно этого эталона (0-100%).
       - Агрегируются метрики: средняя посещаемость по предметам, мин, макс, стд.
    4. Определение курса: Динамический расчет курса на основе года в названии группы.
    
    Args:
        faculty_name (str): Полное название факультета.
        group_base (str): Базовая часть названия группы (без года, напр. "ИСТб").
        target_course (int): Номер курса, для которого будем делать прогноз.
        
    Returns:
        Tuple[pd.DataFrame, QuerySet]: 
            - DataFrame с признаками (features) и таргетами.
            - QuerySet объектов групп (для мета-информации).
            Возвращает (None, None), если данных нет.
    """
    # Фильтрация групп
    groups = StudentGroup.objects.filter(
        speciality__faculty__name=faculty_name,
        name__startswith=group_base
    ).select_related('speciality__faculty')
    
    if not groups.exists():
        return None, None

    group_ids = [g.group_id for g in groups]
    
    # Получение студентов
    students = Student.objects.filter(
        group_id__in=group_ids,
        is_academic=False
    ).select_related('group')
    
    student_ids = [s.student_id for s in students]
    if not student_ids:
        return None, None

    # Сбор и обработка оценок
    results = StudentResult.objects.filter(
        student_id__in=student_ids
    ).select_related('result', 'discipline').values(
        'student_id', 'discipline_id', 'result__result_value'
    )
    
    grades_dict = {} 
    student_discipline_grades = {} 
    
    for r in results:
        sid = r['student_id']
        did = r['discipline_id']
        val = r['result__result_value']
        
        if sid not in grades_dict:
            grades_dict[sid] = []
            student_discipline_grades[sid] = {}
            
        # Нормализация оценки
        grade_val = np.nan
        if val:
            s_val = str(val)
            if 'Зачтено' in s_val and 'Не зачтено' not in s_val:
                grade_val = 5.0
            elif 'Не зачтено' in s_val or 'Н/Я' in s_val:
                grade_val = 2.0
            else:
                try:
                    clean = ''.join(c for c in s_val if c.isdigit() or c == '.')
                    if clean: grade_val = float(clean)
                except: pass
        
        if not np.isnan(grade_val):
            grades_dict[sid].append(grade_val)
            student_discipline_grades[sid][did] = grade_val

    # Расчет посещаемости относительно лидера 
    # Считаем посещения по паре (студент, дисциплина)
    attendance_raw = Attendance.objects.filter(
        student_id__in=student_ids
    ).values('student_id', 'discipline_id').annotate(
        visits=Count('lesson_id')
    )
    
    # Преобразуем в DataFrame для удобной группировки
    df_att = pd.DataFrame(list(attendance_raw))
    if df_att.empty:
        # Если нет данных о посещаемости вообще
        att_metrics = {sid: {
            'overall_attendance_percent': 0,
            'avg_subject_attendance': 0,
            'std_subject_attendance': 0,
            'min_subject_attendance': 0,
            'max_subject_attendance': 0,
            'num_subjects_with_attendance': 0,
            'total_lessons_all': 0,
            'total_attended_all': 0
        } for sid in student_ids}
    else:
        # Находим максимум посещений по каждой дисциплине в рамках выборки
        discipline_max = df_att.groupby('discipline_id')['visits'].transform('max')
        df_att['max_visits_in_discipline'] = discipline_max
        
        # Считаем относительный процент для каждой записи
        df_att['rel_percent'] = np.where(
            df_att['max_visits_in_discipline'] > 0,
            (df_att['visits'] / df_att['max_visits_in_discipline']) * 100,
            0
        )
        
        # Агрегируем метрики по студентам
        att_agg = df_att.groupby('student_id').agg(
            total_attended_all=('visits', 'sum'),
            avg_subject_attendance=('rel_percent', 'mean'),
            std_subject_attendance=('rel_percent', 'std'),
            min_subject_attendance=('rel_percent', 'min'),
            max_subject_attendance=('rel_percent', 'max'),
            num_subjects_with_attendance=('discipline_id', 'count')
        ).fillna(0) 
        
        # Расчет общего процента посещаемости
        df_att['max_possible_for_student'] = df_att.groupby('student_id')['max_visits_in_discipline'].transform('sum')
        overall_agg = df_att.groupby('student_id').apply(
            lambda x: (x['visits'].sum() / x['max_possible_for_student'].iloc[0] * 100) if x['max_possible_for_student'].iloc[0] > 0 else 0
        ).to_frame(name='overall_attendance_percent')
        
        att_agg = att_agg.join(overall_agg)
        att_metrics = att_agg.to_dict('index')

    # Формирование итоговых строк
    data_rows = []
    
    for student in students:
        sid = student.student_id
        group_name = student.group.name
        
        # Определение курса
        match = re.search(r'(\d{2})$', group_name)
        if not match: continue
        year_suffix = int(match.group(1))
        curr_y = datetime.now().year % 100
        century = 2000 if year_suffix <= curr_y else 1900
        entry_year = century + year_suffix
        course = StudentRatingService.calculate_course(entry_year)
        
        if course not in [1, 2, 3, 4]: continue
        
        grades = grades_dict.get(sid, [])
        if not grades: continue # Пропускаем студентов без оценок
        
        # Статистика по оценкам
        avg_grade = np.mean(grades)
        std_grade = np.std(grades) if len(grades) > 1 else 0
        min_grade = np.min(grades)
        max_grade = np.max(grades)
        num_subjects = len(grades)
        
        arr_grades = np.array(grades)
        excellent = np.sum(arr_grades >= 4.5) / num_subjects
        good = np.sum((arr_grades >= 4.0) & (arr_grades < 4.5)) / num_subjects
        satisfactory = np.sum((arr_grades >= 3.0) & (arr_grades < 4.0)) / num_subjects
        poor = np.sum(arr_grades < 3.0) / num_subjects
        
        # Получаем метрики посещаемости 
        metrics = att_metrics.get(sid, {
            'overall_attendance_percent': 0, 'avg_subject_attendance': 0,
            'std_subject_attendance': 0, 'min_subject_attendance': 0,
            'max_subject_attendance': 0, 'num_subjects_with_attendance': 0,
            'total_attended_all': 0
        })

        total_lessons_all = metrics['total_attended_all'] 
        
        data_rows.append({
            'mira_id': sid,
            'student_course': course,
            'avg_grade': avg_grade,
            'std_grade': std_grade,
            'min_grade': min_grade,
            'max_grade': max_grade,
            'num_subjects': num_subjects,
            'excellent_rate': excellent,
            'good_rate': good,
            'satisfactory_rate': satisfactory,
            'poor_rate': poor,
            'unique_grades': len(np.unique(grades)),

            'overall_attendance_percent': metrics['overall_attendance_percent'],
            'avg_subject_attendance': metrics['avg_subject_attendance'],
            'std_subject_attendance': metrics['std_subject_attendance'],
            'min_subject_attendance': metrics['min_subject_attendance'],
            'max_subject_attendance': metrics['max_subject_attendance'],
            'num_subjects_with_attendance': metrics['num_subjects_with_attendance'],

            'total_lessons_all': total_lessons_all, 
            'total_attended_all': metrics['total_attended_all'],
            
            'group': group_name
        })
    
    df = pd.DataFrame(data_rows)
    return df, groups

def run_prediction_pipeline(faculty: str, group_base: str, course: int):
    """
    Основной пайплайн машинного обучения: подготовка, обучение, предсказание, сохранение.
    
    Этапы работы:
    1. Подготовка данных: Вызов `prepare_data_from_db`.
    2. Разделение выборки:
       - Train: Студенты старших курсов (> target_course).
       - Target: Студенты целевого курса (= target_course).
    3. Предобработка: Скалирование признаков (StandardScaler).
    4. Обучение модели:
       - Использование нейросети `GradeRegressor`.
       - 200 эпох, оптимизатор Adam, loss MSE.
       - Валидация на отложенной выборке (20%).
    5. Предсказание: Генерация прогноза для целевой группы.
    6. Пост-обработка:
       - Ограничение прогноза диапазоном [2.0, 5.0].
       - Расчет `change_percent` (прогноз изменения успеваемости).
    7. Сохранение: Экспорт результатов в JSON файл в кэш.
    
    Args:
        faculty (str): Название факультета.
        group_base (str): База названия группы.
        course (int): Целевой курс.
        
    Returns:
        dict: Результат выполнения:
            - "message": Статус успеха/ошибки.
            - "file": Имя сохраненного файла.
            - "count": Количество предсказаний.
            - "sample": Первые 5 записей для превью.
            - "error": (если есть) Описание ошибки.
    """
    print(f"Запуск прогнозирования для {faculty}, группа {group_base}, курс {course}")
    
    df, groups_obj = prepare_data_from_db(faculty, group_base, course)
    
    if df is None or df.empty:
        return {"error": "Нет данных для обучения или предсказания"}

    # Фильтрация целевого курса и обучающей выборки (старшие курсы)
    target_df = df[df['student_course'] == course]
    train_df = df[df['student_course'] > course]
    
    if train_df.empty or target_df.empty:
        return {"error": f"Недостаточно данных. Обучающая: {len(train_df)}, Целевая: {len(target_df)}"}

    feature_cols = [
        'avg_grade', 'std_grade', 'min_grade', 'max_grade',
        'num_subjects', 'excellent_rate', 'good_rate',
        'satisfactory_rate', 'poor_rate', 'unique_grades',
        'total_lessons_all', 'total_attended_all', 'overall_attendance_percent',
        'avg_subject_attendance', 'std_subject_attendance',
        'min_subject_attendance', 'max_subject_attendance',
        'num_subjects_with_attendance'
    ]
    
    missing_cols = set(feature_cols) - set(df.columns)
    if missing_cols:
        for col in missing_cols:
            df[col] = 0
            target_df[col] = 0
            train_df[col] = 0

    X_train = train_df[feature_cols].values
    y_train = train_df['avg_grade'].values
    
    X_target = target_df[feature_cols].values
    
    # Скалирование
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_target_scaled = scaler.transform(X_target)
    
    # Split для валидации
    X_tr, X_val, y_tr, y_val = train_test_split(X_train_scaled, y_train, test_size=0.2, random_state=42)
    
    # DataLoaders
    train_dataset = StudentDataset(X_tr, y_tr)
    val_dataset = StudentDataset(X_val, y_val)
    train_loader = DataLoader(train_dataset, batch_size=16, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=16, shuffle=False)
    
    # Model
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model = GradeRegressor(X_train.shape[1]).to(device)
    criterion = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    
    # Training Loop
    num_epochs = 200
    print("Обучение модели...")
    for epoch in range(num_epochs):
        model.train()
        train_loss = 0
        for batch_X, batch_y in train_loader:
            batch_X, batch_y = batch_X.to(device), batch_y.to(device)
            optimizer.zero_grad()
            preds = model(batch_X)
            loss = criterion(preds, batch_y)
            loss.backward()
            optimizer.step()
            train_loss += loss.item()
        
        model.eval()
        val_loss = 0
        with torch.no_grad():
            for batch_X, batch_y in val_loader:
                batch_X, batch_y = batch_X.to(device), batch_y.to(device)
                val_loss += criterion(model(batch_X), batch_y).item()
        
        if (epoch+1) % 50 == 0:
            print(f"Epoch {epoch+1}: Train Loss = {train_loss/len(train_loader):.4f}, Val Loss = {val_loss/len(val_loader):.4f}")
    
    # Prediction
    model.eval()
    with torch.no_grad():
        X_target_tensor = torch.FloatTensor(X_target_scaled).to(device)
        preds_raw = model(X_target_tensor).cpu().numpy().flatten()
    
    preds_clipped = np.clip(preds_raw, 2.0, 5.0)
    
    # Формирование результата
    results_df = pd.DataFrame({
        'mira_id': target_df['mira_id'],
        'avg_grade_current': target_df['avg_grade'],
        'predicted_grade': preds_clipped,
        'group': target_df['group'],
        'student_course': target_df['student_course']
    })
    
    results_df['change_percent'] = np.where(
        results_df['avg_grade_current'] != 0,
        ((results_df['predicted_grade'] - results_df['avg_grade_current']) / results_df['avg_grade_current']) * 100,
        np.nan
    )
    results_df['change_direction'] = np.select(
        [results_df['change_percent'] > 0, results_df['change_percent'] < 0, results_df['change_percent'] == 0],
        ['positive', 'negative', 'no change'],
        default='undefined'
    )
    
    # Сохранение в JSON для API 
    cache_dir = os.path.join(settings.MEDIA_ROOT, 'prediction_cache')
    os.makedirs(cache_dir, exist_ok=True)
    
    filename = f"predictions_{faculty.replace(' ', '_')}_{group_base}_course{course}.json"
    filepath = os.path.join(cache_dir, filename)
    
    # Конвертация в JSON-сериализуемый формат
    records = results_df.to_dict(orient='records')
    for rec in records:
        for k, v in rec.items():
            if isinstance(v, float):
                rec[k] = round(v, 4)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False)
    
    print(f"Результаты сохранены в {filepath}")
    
    return {
        "message": "Прогноз успешно построен",
        "file": filename,
        "count": len(records),
        "sample": records[:5]
    }