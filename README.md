# IRNTU-Dashboard_django_backend
Проект | Инструменты для обработки открытых данных студентов института ИТиАД

## Запуск проекта
### Создание виртуального окружения: 
```
python3 -m venv env
```
### Активация виртуального окружения:
Windows:

```bash
<Путь к проекту>\env\Scripts\activate.bat
```
```powershell
<Путь к проекту>\env\Scripts\Activate.ps1
```

Linux:
```
source <Путь к проекту>/env/bin/activate
```
### Обновление миграций:
```
python manage.py makemigrations
python manage.py migrate
```

### Запуск сервера:
```
python manage.py runserver
```

### Запуск тестов:
```
pytest application/tests.py -v
```
