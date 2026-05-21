# application/ml_models/predictor.py

import joblib
import numpy as np
from pathlib import Path

class DropoutPredictor:
    def __init__(self):
        model_dir = Path(__file__).parent
        self.model = joblib.load(model_dir / 'dropout_risk_model.pkl')
        self.scaler = joblib.load(model_dir / 'scaler.pkl')
        self.is_loaded = True
    
    def predict(self, avg_grade, attendance_percent, debt_count, debt_ratio=None):
        """Предсказание для одного студента"""
        if debt_ratio is None:
            debt_ratio = debt_count / 15  # Приблизительное значение
        features = np.array([[avg_grade, attendance_percent, debt_count, debt_ratio]])
        features_scaled = self.scaler.transform(features)
        risk = self.model.predict_proba(features_scaled)[0][1]
        return round(risk, 3)
    
    def predict_batch(self, students_data):
        """
        Пакетное предсказание для нескольких студентов.
        students_data: список словарей с ключами:
            - 'avg_grade'
            - 'attendance_percent'
            - 'debt_count'
            - 'debt_ratio' (опционально)
        """
        if not self.is_loaded:
            return [0.5] * len(students_data)
        
        # Собираем все признаки в одну матрицу (4 признака)
        features_list = []
        for data in students_data:
            avg_grade = data.get('avg_grade', 0)
            attendance = data.get('attendance_percent', 0)
            debt_count = data.get('debt_count', 0)
            # 4-й признак: debt_ratio (доля долгов)
            debt_ratio = data.get('debt_ratio', debt_count / max(data.get('total_subjects', 15), 1))
            
            features_list.append([
                avg_grade,
                attendance,
                debt_count,
                debt_ratio
            ])
        
        features = np.array(features_list)
        features_scaled = self.scaler.transform(features)
        risks = self.model.predict_proba(features_scaled)[:, 1]
        
        return [round(float(r), 3) for r in risks]

predictor = DropoutPredictor()