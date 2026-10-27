# AICoach

Приложение, помогающее прогрессировать в видеоиграх

# CS2 Analytics Platform

Локальная версия платформы с регистрацией, входом и личным кабинетом. Загрузка и анализ демок пока не реализованы.

## Требования

macOS, Node.js 20.9 или новее, Python 3.12–3.14 и запущенный Docker Desktop с Compose. Команды ниже выполняются из корня проекта, если не указано иное. Не используйте пример пароля для публичного развёртывания.

## Первоначальная настройка

```bash
cp .env.example .env
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements-lock.txt
.venv/bin/python -m pip install --no-deps -e backend
cd frontend
npm ci
cd ..
docker compose up -d
```

Дождитесь запуска базы (`docker compose ps`), затем примените миграции:

```bash
cd backend
../.venv/bin/alembic upgrade head
cd ..
```

Если команда `docker` не найдена, запустите Docker Desktop и завершите его первоначальную настройку. Если CLI ещё не добавлен в PATH, для текущего окна терминала можно выполнить `export PATH="/Applications/Docker.app/Contents/Resources/bin:$PATH"`. Для постоянной настройки используйте параметры Docker Desktop.

## Запуск

В первом окне терминала:

```bash
cd backend
../.venv/bin/uvicorn app.main:app --reload
```

Во втором окне:

```bash
cd frontend
npm run dev
```

Откройте http://localhost:3000. API доступен на http://localhost:8000, документация — на http://localhost:8000/docs. Используйте `localhost` для обоих адресов: смешивание `localhost` и `127.0.0.1` нарушает работу cookie. `/health` проверяет процесс API, `/ready` дополнительно проверяет базу. Кнопка на странице повторяет проверку `/ready`.

## Аккаунт и кабинет

Откройте главную страницу, выберите «Создать аккаунт», укажите email и пароль длиной от 12 до 256 символов. После регистрации откроется личный кабинет. При обновлении страницы сессия сохраняется; кнопка «Выйти из аккаунта» завершает её на сервере. Вход доступен по ссылке на главной. Подтверждение email и восстановление пароля на этом этапе не реализованы.

Чтобы обновить существующую установку после добавления аккаунтов, из корня проекта выполните:

```bash
.venv/bin/python -m pip install -r backend/requirements-lock.txt
cd backend
../.venv/bin/alembic upgrade head
```

Перезапустите backend и frontend. Тесты аккаунтов создают временные схемы в настроенной PostgreSQL и удаляют их после проверки; база должна быть запущена, а пользователь БД иметь право создавать схемы. Не направляйте тесты на производственную базу.

Для HTTPS настройте `COOKIE_SECURE=true` и `ALLOWED_ORIGINS` в `.env`, например JSON-массив адресов разрешённого frontend. Для локального HTTP оставьте `COOKIE_SECURE=false`. В производстве frontend и API должны быть на одном сайте для работы SameSite-cookie, а CORS — с точным перечнем адресов. `NEXT_PUBLIC_API_URL` задаётся при запуске или сборке frontend; `.env` в корне автоматически читается backend, но не frontend. Для локального запуска используется `http://localhost:8000` по умолчанию.

## Проверки

Из корня проекта:

```bash
cd backend
../.venv/bin/pytest
../.venv/bin/ruff check .
../.venv/bin/alembic current
cd ../frontend
npm run lint
npm run typecheck
npm run build
```

Для ручной проверки состояния остановите базу командой `docker compose stop db` из корня проекта и нажмите «Проверить снова»: страница должна сообщить о недоступности базы. Верните её командой `docker compose start db`. Остановите backend и повторите проверку: страница должна сообщить о недоступности сервера.

Остановка базы: `docker compose down`. Данные сохраняются в томе Docker. Не добавляйте флаг `-v`, если не хотите удалить локальную базу. Если меняете пароль после создания тома, PostgreSQL не применит его автоматически к существующей базе.

Переменные в `.env` предназначены только для локальной разработки; этот файл и файлы в `storage/` исключены из Git. Версии зависимостей зафиксированы в lock-файлах.
