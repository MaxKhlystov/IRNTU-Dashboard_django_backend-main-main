# import pandas as pd
# import psycopg2
# from psycopg2 import sql
# from datetime import datetime

# # Параметры подключения к БД
# DB_CONFIG = {
#     'host': 'localhost',
#     'database': 'project_db',
#     'user': 'postgres',
#     'password': '12345',  # замените на ваш пароль
#     'port': '5432'
# }

# def create_connection():
#     """Создание подключения к БД"""
#     try:
#         conn = psycopg2.connect(**DB_CONFIG)
#         return conn
#     except Exception as e:
#         print(f"Ошибка подключения: {e}")
#         return None

# def insert_faculty_data(conn, df):
#     """Заполнение таблицы faculty"""
#     try:
#         cur = conn.cursor()
        
#         # Получаем уникальные факультеты
#         faculties = df[['Faculty_ID', 'Faculty']].drop_duplicates()
        
#         for _, row in faculties.iterrows():
#             cur.execute(
#                 "INSERT INTO faculty (faculty_id, name) VALUES (%s, %s) ON CONFLICT (faculty_id) DO NOTHING",
#                 (row['Faculty_ID'], row['Faculty'])
#             )
        
#         conn.commit()
#         print(f"Добавлено {len(faculties)} записей в таблицу faculty")
        
#     except Exception as e:
#         conn.rollback()
#         print(f"Ошибка при вставке в faculty: {e}")

# def insert_speciality_data(conn, df):
#     """Заполнение таблицы speciality"""
#     try:
#         cur = conn.cursor()
        
#         # Получаем уникальные специальности
#         specialities = df[['Speciality_ID', 'Speciality', 'Faculty_ID']].drop_duplicates()
        
#         for _, row in specialities.iterrows():
#             cur.execute(
#                 "INSERT INTO speciality (speciality_id, name, faculty_id) VALUES (%s, %s, %s) ON CONFLICT (speciality_id) DO NOTHING",
#                 (row['Speciality_ID'], row['Speciality'], row['Faculty_ID'])
#             )
        
#         conn.commit()
#         print(f"Добавлено {len(specialities)} записей в таблицу speciality")
        
#     except Exception as e:
#         conn.rollback()
#         print(f"Ошибка при вставке в speciality: {e}")

# def insert_student_group_data(conn, df):
#     """Заполнение таблицы student_group"""
#     try:
#         cur = conn.cursor()
        
#         # Получаем уникальные группы
#         groups = df[['Group', 'Speciality_ID']].drop_duplicates()
        
#         # Создаем словарь для сопоставления группы с ID
#         group_id_mapping = {}
        
#         for idx, (_, row) in enumerate(groups.iterrows(), 1):
#             group_name = row['Group']
#             speciality_id = row['Speciality_ID']
            
#             # Вставляем группу и получаем её ID
#             cur.execute(
#                 "INSERT INTO student_group (group_id, name, speciality_id) VALUES (%s, %s, %s) ON CONFLICT (group_id) DO NOTHING",
#                 (idx, group_name, speciality_id)
#             )
#             group_id_mapping[group_name] = idx
        
#         conn.commit()
#         print(f"Добавлено {len(groups)} записей в таблицу student_group")
#         return group_id_mapping
        
#     except Exception as e:
#         conn.rollback()
#         print(f"Ошибка при вставке в student_group: {e}")
#         return {}

# def insert_student_data(conn, df, group_id_mapping):
#     """Заполнение таблицы student"""
#     try:
#         cur = conn.cursor()
        
#         # Получаем уникальных студентов
#         students = df[['student', 'Birthday', 'Is_Academic', 'Group']].drop_duplicates()
        
#         for _, row in students.iterrows():
#             student_id = row['student']
#             birthday = row['Birthday']
#             is_academic = bool(row['Is_Academic'])
#             group_name = row['Group']
            
#             # Получаем ID группы из словаря
#             group_id = group_id_mapping.get(group_name)
            
#             if group_id:
#                 cur.execute(
#                     """INSERT INTO student (student_id, birthday, is_academic, group_id) 
#                     VALUES (%s, %s, %s, %s) ON CONFLICT (student_id) DO NOTHING""",
#                     (student_id, birthday, is_academic, group_id)
#                 )
        
#         conn.commit()
#         print(f"Добавлено {len(students)} записей в таблицу student")
        
#     except Exception as e:
#         conn.rollback()
#         print(f"Ошибка при вставке в student: {e}")

# def insert_discipline_data(conn, df):
#     """Заполнение таблицы discipline"""
#     try:
#         cur = conn.cursor()
        
#         # Получаем уникальные дисциплины
#         disciplines = df[['discipline_id', 'Discipline']].drop_duplicates()
        
#         for _, row in disciplines.iterrows():
#             cur.execute(
#                 "INSERT INTO discipline (discipline_id, name) VALUES (%s, %s) ON CONFLICT (discipline_id) DO NOTHING",
#                 (row['discipline_id'], row['Discipline'])
#             )
        
#         conn.commit()
#         print(f"Добавлено {len(disciplines)} записей в таблицу discipline")
        
#     except Exception as e:
#         conn.rollback()
#         print(f"Ошибка при вставке в discipline: {e}")

# def insert_result_type_data(conn, df):
#     """Заполнение таблицы result_type"""
#     try:
#         cur = conn.cursor()
        
#         # Получаем уникальные типы результатов
#         result_types = df[['Result_ID', 'Result']].drop_duplicates()
        
#         for _, row in result_types.iterrows():
#             result_id = row['Result_ID']
#             result_value = row['Result']
            
#             # Пропускаем NaN значения
#             if pd.isna(result_id):
#                 continue
                
#             cur.execute(
#                 "INSERT INTO result_type (result_id, result_value) VALUES (%s, %s) ON CONFLICT (result_id) DO NOTHING",
#                 (int(result_id), str(result_value))
#             )
        
#         conn.commit()
#         print(f"Добавлено {len(result_types)} записей в таблицу result_type")
        
#     except Exception as e:
#         conn.rollback()
#         print(f"Ошибка при вставке в result_type: {e}")

# def insert_student_result_data(conn, df):
#     """Заполнение таблицы student_result"""
#     try:
#         cur = conn.cursor()
        
#         # Обрабатываем каждую запись
#         for _, row in df.iterrows():
#             student_id = row['student']
#             discipline_id = row['discipline_id']
#             result_id = row['Result_ID']
            
#             # Пропускаем записи с NaN в Result_ID
#             if pd.isna(result_id):
#                 continue
                
#             cur.execute(
#                 """INSERT INTO student_result (student_id, discipline_id, result_id) 
#                 VALUES (%s, %s, %s) ON CONFLICT (student_id, discipline_id) DO NOTHING""",
#                 (student_id, discipline_id, int(result_id))
#             )
        
#         conn.commit()
#         print(f"Добавлено {len(df)} записей в таблицу student_result")
        
#     except Exception as e:
#         conn.rollback()
#         print(f"Ошибка при вставке в student_result: {e}")

# def insert_attendance_data(conn, df):
#     """Заполнение таблицы attendance с проверкой внешних ключей"""
#     try:
#         cur = conn.cursor()
        
#         # Получаем существующие ID из связанных таблиц
        
#         cur.execute("SELECT student_id FROM student")
#         existing_students = {row[0] for row in cur.fetchall()}
        
#         cur.execute("SELECT discipline_id FROM discipline")
#         existing_disciplines = {row[0] for row in cur.fetchall()}
        
        
#         # Подготовка данных для вставки
#         attendance_data = []
#         skipped_records = 0
        
#         for _, row in df.iterrows():
#             # Проверяем наличие необходимых данных и внешних ключей
#             if ( 
#                 int(row['student']) in existing_students and
#                 int(row['discipline_id']) in existing_disciplines):
                
                
#                 attendance_record = (
#                     int(row['lesson_id']),
#                     int(row['student']),
#                     row['created_at'],
#                     row['updated_at'],
#                     int(row['user_id']),
#                     int(row['discipline_id'])
#                 )
#                 attendance_data.append(attendance_record)
#             else:
#                 skipped_records += 1
        
#         # Вставляем данные
#         insert_query = """
#         INSERT INTO attendance (lesson_id, student_id, created_at, updated_at, user_id, discipline_id) 
#         VALUES (%s, %s, %s, %s, %s, %s) 
#         ON CONFLICT (lesson_id, student_id) DO NOTHING
#         """
        
#         cur.executemany(insert_query, attendance_data)
#         conn.commit()
#         print(f"Успешно добавлено {len(attendance_data)} записей в таблицу attendance")
#         print(f"Пропущено {skipped_records} записей из-за отсутствия внешних ключей или данных")
        
#     except Exception as e:
#         conn.rollback()
#         print(f"Ошибка при вставке в attendance: {e}")

# def main():
#     # Загрузка данных из CSV
#     print("Загрузка данных из CSV...")
#     df = pd.read_csv(r'C:\Users\Kopikou\Desktop\Result_2.csv')
#     print(f"Загружено {len(df)} записей")
    
#     # Подключение к БД
#     print("Подключение к базе данных...")
#     conn = create_connection()
#     if not conn:
#         return
    
#     try:
#         # Заполняем таблицы в правильном порядке (с учетом внешних ключей)
#         # insert_faculty_data(conn, df)
#         # insert_speciality_data(conn, df)
#         # group_id_mapping = insert_student_group_data(conn, df)
#         # insert_student_data(conn, df, group_id_mapping)
#         # insert_discipline_data(conn, df)
#         # insert_result_type_data(conn, df)
#         # insert_student_result_data(conn, df)
#         insert_attendance_data(conn, df)
        
#         print("Все данные успешно загружены в базу данных!")
        
#     except Exception as e:
#         print(f"Произошла ошибка: {e}")
#     finally:
#         conn.close()

# if __name__ == "__main__":
#     main()



import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime
import os

# === Конфигурация ===
DB_CONFIG = {
    'host': 'localhost',
    'database': 'project_db',
    'user': 'postgres',
    'password': '12345',
    'port': '5432'
}

ATTENDANCE_FILE = 'merged_attendance.csv'
STUDENTS_FILE = 'export_studs_cleaned.csv'

# === Вспомогательные функции ===
def safe_str(value):
    return str(value).strip() if pd.notna(value) else None

def safe_int(value):
    try:
        return int(float(value)) if pd.notna(value) else None
    except (ValueError, TypeError):
        return None

def safe_bool(value):
    return bool(value) if pd.notna(value) else False

def parse_datetime_safe(dt_str):
    if pd.isna(dt_str):
        return None
    try:
        dt_clean = str(dt_str).split('+')[0].strip()
        return datetime.fromisoformat(dt_clean.replace(' ', 'T'))
    except Exception:
        return None

# === Основной скрипт ===
def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    print("1. Загрузка структуры из export_studs_cleaned.csv...")

    if not os.path.exists(STUDENTS_FILE):
        raise FileNotFoundError(f"Файл {STUDENTS_FILE} не найден!")

    df_students = pd.read_csv(STUDENTS_FILE)

    # --- 1. Faculty ---
    faculties = {(safe_int(r['Faculty_ID']), safe_str(r['Faculty'])) for _, r in df_students.iterrows()
                if safe_int(r['Faculty_ID']) is not None and safe_str(r['Faculty'])}
    if faculties:
        execute_values(
            cur,
            "INSERT INTO faculty (faculty_id, name) VALUES %s ON CONFLICT (faculty_id) DO NOTHING",
            list(faculties)
        )
    print(f" → Факультетов: {len(faculties)}")

    # --- 2. Speciality ---
    specialities = {(safe_int(r['Speciality_ID']), safe_str(r['Speciality']), safe_int(r['Faculty_ID']))
                   for _, r in df_students.iterrows()
                   if all(x is not None for x in [safe_int(r['Speciality_ID']), safe_str(r['Speciality']), safe_int(r['Faculty_ID'])])}
    if specialities:
        execute_values(
            cur,
            "INSERT INTO speciality (speciality_id, name, faculty_id) VALUES %s ON CONFLICT (speciality_id) DO NOTHING",
            list(specialities)
        )
    print(f" → Специальностей: {len(specialities)}")

    # --- 3. Student Group ---
    groups = {(safe_str(r['Group']), safe_int(r['Speciality_ID']))
              for _, r in df_students.iterrows()
              if safe_str(r['Group']) and safe_int(r['Speciality_ID']) is not None}
    if groups:
        execute_values(
            cur,
            "INSERT INTO student_group (name, speciality_id) VALUES %s ON CONFLICT (name, speciality_id) DO NOTHING",
            list(groups)
        )
    print(f" → Групп: {len(groups)}")

    # --- 4. Получаем маппинг group_name → group_id ---
    cur.execute("SELECT group_id, name FROM student_group")
    name_to_group_id = {name: gid for gid, name in cur.fetchall()}

    # --- 5. Student ---
    students = []
    for _, row in df_students.iterrows():
        sid = safe_int(row['Student_ID'])
        birthday = safe_str(row['Birthday'])
        is_academic = safe_bool(row['Is_Academic'])
        group_name = safe_str(row['Group'])

        if sid is None or group_name is None or group_name not in name_to_group_id:
            continue

        students.append((sid, birthday, is_academic, name_to_group_id[group_name]))

    if students:
        execute_values(
            cur,
            "INSERT INTO student (student_id, birthday, is_academic, group_id) VALUES %s ON CONFLICT (student_id) DO NOTHING",
            students
        )
    print(f" → Студентов: {len(students)}")

    # --- 6. Discipline из студентов ---
    disciplines_stud = {(safe_int(r['Discipline_ID']), safe_str(r['Discipline']))
                       for _, r in df_students.iterrows()
                       if safe_int(r['Discipline_ID']) is not None and safe_str(r['Discipline'])}
    if disciplines_stud:
        execute_values(
            cur,
            "INSERT INTO discipline (discipline_id, name) VALUES %s ON CONFLICT (discipline_id) DO NOTHING",
            list(disciplines_stud)
        )
    print(f" → Дисциплин из студентов: {len(disciplines_stud)}")

    # --- 7. Result Type ---
    result_types = [(0, "Н/Я"), (1, "Не зачтено"), (2, "2"), (3, "3"), (4, "4"), (5, "5"), (6, "Зачтено")]
    execute_values(
        cur,
        "INSERT INTO result_type (result_id, result_value) VALUES %s ON CONFLICT (result_id) DO NOTHING",
        result_types
    )

    # --- 8. Student Result ---
    results = []
    for _, row in df_students.iterrows():
        student_id = safe_int(row['Student_ID'])
        discipline_id = safe_int(row['Discipline_ID'])
        result_raw = safe_str(row['Result'])

        if student_id is None or discipline_id is None or result_raw is None:
            continue

        if result_raw == "Зачтено":
            result_id = 6
        elif result_raw in ["2", "3", "4", "5"]:
            result_id = int(result_raw)
        elif result_raw == "Не зачтено":
            result_id = 1
        else:
            result_id = 0

        results.append((student_id, discipline_id, result_id))

    if results:
        execute_values(
            cur,
            "INSERT INTO student_result (student_id, discipline_id, result_id) VALUES %s ON CONFLICT (student_id, discipline_id) DO NOTHING",
            results
        )
    print(f" → Результатов: {len(results)}")

    # === 9. Загрузка attendance ===
    print("2. Загрузка посещаемости из merged_attendance.csv...")

    if not os.path.exists(ATTENDANCE_FILE):
        raise FileNotFoundError(f"Файл {ATTENDANCE_FILE} не найден!")

    df_att = pd.read_csv(ATTENDANCE_FILE)

    # --- Дисциплины из attendance ---
    disciplines_att = {(safe_int(r['discipline_id']), safe_str(r.get('discipline', f'Дисциплина {safe_int(r["discipline_id"])}')))
                      for _, r in df_att.iterrows()
                      if safe_int(r['discipline_id']) is not None}
    if disciplines_att:
        execute_values(
            cur,
            "INSERT INTO discipline (discipline_id, name) VALUES %s ON CONFLICT (discipline_id) DO NOTHING",
            list(disciplines_att)
        )
    print(f" → Дисциплин из attendance: {len(disciplines_att)}")

    # --- Обновляем маппинг групп (на случай, если что-то изменилось) ---
    cur.execute("SELECT group_id, name FROM student_group")
    name_to_group_id = {name: gid for gid, name in cur.fetchall()}

    # --- Получаем существующих студентов ---
    cur.execute("SELECT student_id FROM student")
    existing_students = set(row[0] for row in cur.fetchall())

    # --- Обрабатываем attendance ---
    new_students = []
    attendances = []
    skipped = 0

    for _, row in df_att.iterrows():
        lesson_id = safe_int(row['lesson_id'])
        student_id = safe_int(row['mira_id'])
        user_id = safe_int(row['user_id'])
        discipline_id = safe_int(row['discipline_id'])
        group_name = safe_str(row['grup'])

        # Создаём студента, если его нет, но группа известна
        if student_id not in existing_students:
            if group_name in name_to_group_id:
                group_id = name_to_group_id[group_name]
                new_students.append((student_id, None, False, group_id))
                existing_students.add(student_id)  # чтобы не дублировать в этом же цикле
            else:
                skipped += 1
                continue

        # Добавляем запись посещаемости
        created_at = parse_datetime_safe(row.get('created_at'))
        updated_at = parse_datetime_safe(row.get('updated_at'))
        attendances.append((lesson_id, student_id, created_at, updated_at, user_id, discipline_id))

    # Вставляем новых студентов
    if new_students:
        execute_values(
            cur,
            "INSERT INTO student (student_id, birthday, is_academic, group_id) VALUES %s ON CONFLICT (student_id) DO NOTHING",
            new_students
        )
        print(f" → Новых студентов из attendance: {len(new_students)}")

    # Вставляем посещаемость
    if attendances:
        execute_values(
            cur,
            """INSERT INTO attendance 
               (lesson_id, student_id, created_at, updated_at, user_id, discipline_id) 
               VALUES %s 
               ON CONFLICT (lesson_id, student_id) DO NOTHING""",
            attendances
        )
    print(f" → Записей посещаемости: {len(attendances)}")
    print(f" → Пропущено: {skipped}")

    # Сохраняем всё
    conn.commit()
    cur.close()
    conn.close()

    print("\nЗагрузка завершена успешно!")

if __name__ == "__main__":
    main()