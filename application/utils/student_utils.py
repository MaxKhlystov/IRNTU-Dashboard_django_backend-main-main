from datetime import datetime
from typing import Optional

def extract_year_from_group_name(name: str) -> Optional[int]:
    try:
        parts = name.split('-')
        if len(parts) < 2:
            return None
        year_part = parts[1][:2]
        year_suffix = int(year_part)
        current_year = datetime.now().year % 100
        century = 2000 if year_suffix <= current_year else 1900
        return century + year_suffix
    except (IndexError, ValueError, AttributeError):
        return None

def calculate_course(year_of_admission: int) -> int:
    now = datetime.now()
    current_year = now.year
    current_month = now.month
    if current_month < 9:
        return current_year - year_of_admission
    else:
        return current_year - year_of_admission + 1

def student_is_still_enrolled(year_of_admission: int) -> bool:
    now = datetime.now()
    expected_graduation_year = year_of_admission + 4
    return now.year < expected_graduation_year or (now.year == expected_graduation_year and now.month < 7)