# urfu.new-year

Новогодний бот для УрФУ и других ВУЗов.

## Возможности

- регистрация и профиль участника
- новогодняя елка с поздравлениями
- модерация заявок и жалоб

## Стек

- Python 3.13.3, aiogram 3
- PostgreSQL, async SQLAlchemy и Alembic (появятся в следующих задачах)
- pytest и pytest-asyncio

## Требования

- Python 3.13+
- PostgreSQL (для продакшена)

## Быстрый старт

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # Linux/macOS
pip install -r requirements-dev.txt
copy .env.example .env        # Windows
cp .env.example .env          # Linux/macOS
python run.py
```

Перед запуском заполните `.env` по образцу `.env.example`.

## Тесты

```bash
python -m pytest
```

Запускайте тесты из корня проекта.

## Структура

```text
run.py            # единственная точка входа
app/handlers/     # по одному модулю на команду
app/keyboards/    # клавиатуры
app/content/      # тексты для пользователя
security/         # проверки и защита от спама
migrations/       # миграции Alembic
tests/            # тесты
openspec/         # спецификации и файлы задач
```

## Разработка

Новые задачи и изменения сначала описываются в `openspec/`.

## Статус

Проект находится в активной разработке.

## Лицензия

Проект распространяется по лицензии из файла `LICENSE`.


## Changelog

- 2026-11-22: README update

- 2026-11-23: README update

- 2026-11-24: README update

- 2026-11-25: README update
