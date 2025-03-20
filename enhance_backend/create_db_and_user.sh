#!/bin/bash

# Загружаем переменные из .env
export $(cat ../.env | grep -v '^#' | xargs)

# Проверяем, что переменные загружены
echo "DB_USER: $DB_USER"
echo "DB_PASSWORD: $DB_PASSWORD"
echo "DB_NAME: $DB_NAME"
echo "postgres_admin: $PGPASSWORD"
# Устанавливаем переменную окружения для пароля

# Пытаемся подключиться к PostgreSQL как суперпользователь
echo "Создание пользователя и базы данных..."

# Создание пользователя и базы данных
psql -U postgres -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';"
psql -U postgres -c "CREATE DATABASE $DB_NAME;"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"
psql -U postgres -d "$DB_NAME" -c "GRANT ALL ON SCHEMA public TO $DB_USER;"
psql -U postgres -d "$DB_NAME" -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO $DB_USER;"
psql -U postgres -d "$DB_NAME" -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO $DB_USER;"
psql -U postgres -d "$DB_NAME" -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO $DB_USER;"



# Проверяем, что всё прошло успешно
echo "Пользователь $DB_USER и база данных $DB_NAME созданы."
echo "Нажмите любую клавишу для выхода..."
read -n 1 -s