import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.ensemble import RandomForestClassifier
from django.db import connection
from django.core.management.base import BaseCommand
from sklearn.cluster import KMeans
from sklearn.metrics import pairwise_distances
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.compose import ColumnTransformer
############ СТАРАЯ АНАЛИТИКА, УЖЕ НЕ ИСПОЛЬЗУЕТСЯ
def parse_subject_grades(grade_str):
    import pandas as pd
    if pd.isna(grade_str):
        return {}
    parts = grade_str.split(';')
    grades = {}
    for part in parts:
        if ':' in part:
            subject, grade = part.strip().split(':')
            grades[subject.strip()] = float(grade.strip())
    return grades

class Command(BaseCommand):
    help = 'Run analytics script'
    def get_students_from_db(self):
        query = """
            WITH SemesterGrades AS (
                SELECT 
                    gd.Student_ID,
                    hps.Semester,
                    AVG(CAST(gd.Grade AS DECIMAL(10,2))) AS Avg_Grade
                FROM Grades gd
                JOIN Form_control fc ON gd.FC_ID = fc.FC_ID
                JOIN Hours_per_semest hps ON fc.HPS_ID = hps.HPS_ID
                WHERE 
                    fc.Form != 'Зачет' 
                    AND TRY_CAST(gd.Grade AS DECIMAL(10,2)) IS NOT NULL
                GROUP BY gd.Student_ID, hps.Semester
            )

            SELECT 
                sp.Title AS Speciality,
                g.Title AS Group_Name,
                s.Student_ID,
                s.Name,
                DATEDIFF(YEAR, s.Birth_date, GETDATE()) AS Age,
                CASE WHEN a.Student_ID IS NOT NULL THEN 1 ELSE 0 END AS Is_Academic, 
                s.Middle_value_of_sertificate, 
                s.Entry_score, 
                COALESCE(r.Score, 0) AS Rating_score,
                dpl.Grade AS Diploma_grade,

                -- Оценки по семестрам
                COALESCE(MAX(CASE WHEN sg.Semester = 1 THEN sg.Avg_Grade END), 0) AS Semester_1_Grade,
                COALESCE(MAX(CASE WHEN sg.Semester = 2 THEN sg.Avg_Grade END), 0) AS Semester_2_Grade,
                COALESCE(MAX(CASE WHEN sg.Semester = 3 THEN sg.Avg_Grade END), 0) AS Semester_3_Grade,
                COALESCE(MAX(CASE WHEN sg.Semester = 4 THEN sg.Avg_Grade END), 0) AS Semester_4_Grade,
                COALESCE(MAX(CASE WHEN sg.Semester = 5 THEN sg.Avg_Grade END), 0) AS Semester_5_Grade,
                COALESCE(MAX(CASE WHEN sg.Semester = 6 THEN sg.Avg_Grade END), 0) AS Semester_6_Grade,
                COALESCE(MAX(CASE WHEN sg.Semester = 7 THEN sg.Avg_Grade END), 0) AS Semester_7_Grade,
                COALESCE(MAX(CASE WHEN sg.Semester = 8 THEN sg.Avg_Grade END), 0) AS Semester_8_Grade,

                -- Список долгов
                COALESCE(( 
                    SELECT DISTINCT dsc.Disciple_name + ', ' 
                    FROM Debts d 
                    JOIN Hours_per_semest hps ON d.HPS_ID = hps.HPS_ID 
                    JOIN Disciples dsc ON hps.Disciple_ID = dsc.Disciple_ID 
                    WHERE d.Student_ID = s.Student_ID 
                    FOR XML PATH(''), TYPE).value('.', 'NVARCHAR(MAX)'), 'Нет долгов') AS Debts_List,

                -- Средняя оценка за практику
                COALESCE(( 
                    SELECT AVG(CAST(p.Grade AS DECIMAL(10,2))) 
                    FROM Practise p 
                    WHERE p.Student_ID = s.Student_ID 
                ), 0) AS Avg_Practise_Grade,

                -- Средняя посещаемость
                COALESCE(( 
                    SELECT AVG(att.Percent_of_attendance) 
                    FROM Attendance att 
                    WHERE att.Student_ID = s.Student_ID 
                ), 0) AS Avg_Attendance,

                -- Все оценки по предметам
                COALESCE((
                    SELECT 
                        STUFF((
                            SELECT '; ' + dsc.Disciple_name + ': ' + CAST(gd.Grade AS NVARCHAR)
                            FROM Grades gd
                            JOIN Form_control fc ON gd.FC_ID = fc.FC_ID
                            JOIN Hours_per_semest hps ON fc.HPS_ID = hps.HPS_ID
                            JOIN Disciples dsc ON hps.Disciple_ID = dsc.Disciple_ID
                            WHERE gd.Student_ID = s.Student_ID
                            AND fc.Form != 'Зачет'
                            AND TRY_CAST(gd.Grade AS DECIMAL(10,2)) IS NOT NULL
                            FOR XML PATH(''), TYPE).value('.', 'NVARCHAR(MAX)'), 1, 2, '')
                ), 'Нет оценок') AS All_Grades_Per_Subject

                FROM Student s
                JOIN [Group] g ON s.Group_ID = g.Group_ID
                JOIN Education_plan ep ON g.Plan_ID = ep.Plan_ID
                JOIN Specialty sp ON ep.Code = sp.Code
                LEFT JOIN Academ a ON s.Student_ID = a.Student_ID
                LEFT JOIN Rating r ON s.Rating_ID = r.Rating_ID  
                LEFT JOIN Diploma dpl ON s.Student_ID = dpl.Student_ID
                LEFT JOIN SemesterGrades sg ON s.Student_ID = sg.Student_ID

                GROUP BY 
                    sp.Title, g.Title, s.Student_ID, s.Name, s.Birth_date, 
                    s.Middle_value_of_sertificate, s.Entry_score, r.Score, 
                    dpl.Grade, a.Student_ID

                ORDER BY s.Student_ID;
            """
            
        with connection.cursor() as cursor:
            cursor.execute(query)
            columns = [col[0] for col in cursor.description]
            data = cursor.fetchall()
            
            return pd.DataFrame(data, columns=columns)

    def handle(self, *args, **options):
        
        #students = pd.read_csv('project_db.csv', sep=';')
        students = self.get_students_from_db()

        # Функция для парсинга строки в словарь
        def parse_subject_grades(grade_str):
            if pd.isna(grade_str):
                return {}
            parts = grade_str.split(';')
            grades = {}
            for part in parts:
                if ':' in part:
                    subject, grade = part.strip().split(':')
                    grades[subject.strip()] = float(grade.strip())
            return grades

        # Применим ко всем строкам
        students['Grades_Dict'] = students['All_Grades_Per_Subject'].apply(parse_subject_grades)


        def mean_grade(grades_dict):
            if not grades_dict:
                return None
            return sum(grades_dict.values()) / len(grades_dict)


        students['Mean_Subject_Grade'] = students['Grades_Dict'].apply(mean_grade)

        debts_list=[]
        for i in range(len(students)):
            debts_list.append(students['Debts_List'][i].split(','))


        for i in range(len(students)):
            if isinstance(students['Grades_Dict'][i], dict) and isinstance(debts_list[i], list):
                for subject in debts_list[i]:
                    subject = subject.strip()  # удаляем лишние пробелы
                    if subject in students['Grades_Dict'][i]:
                        students['Grades_Dict'][i][subject] = 'Долг'

        # Добавляем отдельные столбцы для предметов и оценок
        all_subjects = set()  # Используем множество для уникальных предметов
        for grades_dict in students['Grades_Dict']:
            all_subjects.update(grades_dict.keys())

        for subject in all_subjects:
            students[subject] = None

        for index, row in students.iterrows():
            grades_dict = row['Grades_Dict']
            for subject, grade in grades_dict.items():
                students.loc[index, subject] = grade

        # Заменяем NaN и None на 0 во всей таблице
        students = students.fillna(0)


        # 1. Подготовка данных для кластеризации (3 курс)
        semester_5_6_data = students.iloc[364:524].copy()  # Копируем данные студентов 3 курса

        # 2. Выбор признаков для кластеризации (только предметы 3 курса)
        all_subjects_3rd_year = set()
        for grades_dict in semester_5_6_data['Grades_Dict']:  # Итерируемся только по данным 3 курса
            all_subjects_3rd_year.update(grades_dict.keys())  # Добавляем все предметы 3 курса в множество

        features_for_clustering = list(all_subjects_3rd_year)  # Преобразуем множество в список

        # 3. Замена "Долг" на -1 (без изменений)
        for subject in features_for_clustering:  # Итерируемся по предметам 3 курса
            semester_5_6_data[subject] = semester_5_6_data[subject].replace('Долг', -1).astype(float) 

        # 4. Обработка нулей (замена на NaN)
        for subject in features_for_clustering:  # Итерируемся по предметам 3 курса
            semester_5_6_data[subject] = semester_5_6_data[subject].replace(0, np.nan) 


        # 5. Масштабирование данных (с использованием маски для исключения NaN)
        numeric_data = semester_5_6_data[features_for_clustering].copy()  # Копируем данные для масштабирования

        # Создание маски (исключает NaN)
        mask = ~numeric_data.isna()  # True, если значение не NaN

        scaler = StandardScaler()  # Создаем объект StandardScaler
        scaled_values = scaler.fit_transform(numeric_data[mask])  # Масштабируем данные, используя маску
        numeric_data[mask] = scaled_values  # Возвращаем масштабированные данные в DataFrame
        scaled_data = numeric_data  # Переименовываем для ясности

        # 6. Определение оптимального числа кластеров (метод локтя)
        inertia = []  # Список для хранения значений инерции
        for k in range(1, 11):  # Проверяем k от 1 до 10
            kmeans = KMeans(n_clusters=k, random_state=42)  # Создаем объект KMeans
            kmeans.fit(scaled_data.fillna(0))  # Заполняем NaN нулями только для метода локтя и обучаем модель
            inertia.append(kmeans.inertia_)  # Добавляем значение инерции в список



        k = 2  # Выбираем k на основе графика (хотя там вообще один кластер можно бы поставить)

        # 7. Применение KMeans для кластеризации предметов (с учетом NaN и транспонированием)
        def nan_euclidean_distance(X, Y):  # Функция для вычисления расстояния с учетом NaN
            return np.sqrt(np.nansum((X - Y)**2, axis=0))  # axis=0 для кластеризации предметов

        scaled_data_transposed = scaled_data.T  # Транспонируем данные для кластеризации предметов

        kmeans = KMeans(n_clusters=k, random_state=42)  # Создаем объект KMeans
        distance_matrix = pairwise_distances(scaled_data_transposed.fillna(0), metric=nan_euclidean_distance)  # Вычисляем матрицу расстояний, заполняя NaN нулями только здесь

        kmeans.fit(distance_matrix)  # Обучаем KMeans на матрице расстояний
        subject_clusters = kmeans.labels_  # Получаем метки кластеров для предметов

        # 8. Добавление информации о кластерах для предметов
        subject_cluster_mapping = dict(zip(all_subjects_3rd_year, subject_clusters)) # Создаем словарь {предмет: номер_кластера}




        # 1. Подготовка данных (3 курс)
        semester_5_6_data = students.iloc[364:728].copy()

        # 2. Выбор признаков (только предметы 3 курса)
        all_subjects_3rd_year = set()
        for grades_dict in semester_5_6_data['Grades_Dict']:
            all_subjects_3rd_year.update(grades_dict.keys())
        features_for_clustering = list(all_subjects_3rd_year)


        # 3. Замена "Долг" на -1
        for subject in features_for_clustering:
            semester_5_6_data[subject] = semester_5_6_data[subject].replace('Долг', -1).astype(float)

        # 5. Масштабирование данных 
        numeric_data = semester_5_6_data[features_for_clustering].copy()  # Копируем данные для масштабирования

        # Создание маски (исключает NaN)
        mask = ~numeric_data.isna()  # True, если значение не NaN

        scaler = StandardScaler()  # Создаем объект StandardScaler
        scaled_values = scaler.fit_transform(numeric_data[mask])  # Масштабируем данные, используя маску
        numeric_data[mask] = scaled_values  # Возвращаем масштабированные данные в DataFrame
        scaled_data = numeric_data  # Переименовываем для ясности


        def prepare_data(students):
            # Создаем отдельные колонки для каждого предмета
            all_subjects = set()
            for grades in students['Grades_Dict']:
                all_subjects.update(grades.keys())
            
            for subject in all_subjects:
                students[subject] = students['Grades_Dict'].apply(lambda x: x.get(subject, np.nan))
            
            # Обработка долгов и пропущенных значений
            students.replace('Долг', -1, inplace=True)
            students.fillna(0, inplace=True)
            return students, list(all_subjects)

        # Загрузка данных
        students = self.get_students_from_db()
        students['Grades_Dict'] = students['All_Grades_Per_Subject'].apply(
            lambda x: {} if pd.isna(x) else {s.strip(): float(g.strip()) 
                                        for part in x.split(';') 
                                        if ':' in part 
                                        for s, g in [part.strip().split(':')]})

        students, all_subjects = prepare_data(students)

        # Разделение на курсы
        train_data = students.iloc[364:524].copy() 
        predict_data = students.iloc[525:760].copy()  

        # Определяем общие предметы
        common_subjects = list(set(train_data.columns).intersection(set(predict_data.columns)) & set(all_subjects))

        # --- Обучение и предсказание ---

        # Создаем пайплайн для обработки данных
        preprocessor = ColumnTransformer(
            transformers=[
                ('imputer', SimpleImputer(strategy='mean'), common_subjects)
            ])

        predictions = pd.DataFrame(index=predict_data.index)

        for subject in common_subjects:
            # Подготовка данных
            X_train = train_data[common_subjects]
            y_train = train_data[subject]
            
            # Явно создаем 5 категорий (включая долги)
            y_train_cat = pd.cut(y_train,
                                bins=[-2, -0.5, 2.5, 3.5, 4.5, 5.5],
                                labels=['Долг', '2', '3', '4', '5'],
                                include_lowest=True)  # Важно!
            
            # Удаляем только нули (не трогая долги)
            valid_idx = (y_train != 0) | (y_train == -1)  # Сохраняем и оценки, и долги
            X_train = X_train[valid_idx]
            y_train_cat = y_train_cat[valid_idx].dropna()
            
            if len(y_train_cat) < 10:
                print(f"Недостаточно данных для предмета {subject}")
                continue
            
            # Создаем и обучаем модель
            model = make_pipeline(
                preprocessor,
                RandomForestClassifier(random_state=42)
            )
            model.fit(X_train, y_train_cat)
            
            # Предсказание
            X_predict = predict_data[common_subjects]
            y_pred = model.predict(X_predict)
            predictions[subject] = y_pred

        # Добавляем предсказания
        predict_data = pd.concat([predict_data, predictions.add_prefix('Predicted_')], axis=1)

        # --- Визуализация ---

        def show_student_predictions(student_id):
            student = predict_data[predict_data['Student_ID'] == student_id].iloc[0]
            pred_grades = student.filter(like='Predicted_').copy() # <--- Создаем копию!
            
            # Теперь изменяем индекс копии
            pred_grades.index = pred_grades.index.str.replace('Predicted_', '')
            
            # Создаем DataFrame для визуализации (важно!)
            grades_df = pd.DataFrame({
                'Предмет': pred_grades.index,
                'Результат': pred_grades.values
            })

            order = ['Долг', '2', '3', '4', '5']
            grades_df['Результат'] = grades_df['Результат'].astype('category').cat.set_categories(order)
            

            
            

        def analyze_student(student_id):
            student = predict_data[predict_data['Student_ID'] == student_id].iloc[0]
            pred_grades = student.filter(like='Predicted_')
        

        # Пример использования
        show_student_predictions(495)
        analyze_student(495)

        # Сохранение результатов
        #predict_data.to_csv('student_predictions_with_debts.csv', index=False)

        # Выбираем нужные столбцы
        columns_to_keep = [
            'Student_ID', 'Name', 'Age', 'Group_Name', 'Speciality',
            'Middle_value_of_sertificate', 'Entry_score', 'Rating_score',
            'Diploma_grade', 'Is_Academic'
        ] + [col for col in predict_data.columns if col.startswith('Predicted_')]

        # Создаем DataFrame с нужными столбцами
        result_data = predict_data[columns_to_keep].copy()

        # Переименование: удаляем 'Predicted_' только из предметов
        new_columns = []
        for col in result_data.columns:
            if col.startswith("Predicted_"):
                new_columns.append(col.replace("Predicted_", ""))
            else:
                new_columns.append(col)

        result_data.columns = new_columns

        # Сохраняем в CSV
        result_data.to_csv('application/management/predictions_results.csv', index=False, sep=';', encoding='utf-8')

