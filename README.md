# Сервис микроблогов
Корпоративный сервис микроблогов 

![Logotype](dist/favicon.ico)

## Установка (Linux)

1. клонируем репозиторий 

```git clone https://gitlab.skillbox.ru/denis_dorokhov_1/python_advanced_diploma.git```

2. Создание виртуального окружения

```python3 -m venv venv```

3. Активация виртуального окружения

```source venv/bin/activate```

4. Установка зависимостей

```pip install -r requirements.txt```

5. Запуск Docker-контейнера с приложением

```docker-compose up```

После запуска, приложение доступно по [адресу](http://localhost:8000)

## Тесты

1. Запустить отдельный Docker файл, чтобы создалась отдельная БД в Postgres
```docker-compose -f docker-compose.test.yaml up -d```

2. Перейти в директорию с тестами
```cd app/test```

3. Запустить тесты
```pytest```

Все маркеры для тестов описаны в 
```app/test/pytest.ini```

## Стек технологий

- Backend: FastAPI (Python 3.12)

- База данных: PostgreSQL + SQLAlchemy (Async)

- Контейнеризация: Docker & Docker Compose

## Возможности сервиса
- Аутентификация пользователей по API-ключам
- Публикация твитов с текстовым содержанием и изображениями или без них
- Система лайков и подписок на других пользователей
- Просмотр ленты твитов
- Загрузка и хранение медиафайлов