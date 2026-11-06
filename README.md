# urfu.new-year

Новогодний бот для УрФУ.

## Стек

- Python 3.13.3, aiogram 3
- PostgreSQL, async SQLAlchemy и Alembic (появятся в следующих задачах)
- pytest и pytest-asyncio

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

## Тесты

```bash
python -m pytest
```

## Структура

```text
run.py            # единственная точка входа
app/handlers/     # по одному модулю на команду
app/keyboards/    # клавиатуры
app/content/      # тексты для пользователя
tests/            # тесты
openspec/         # спецификации и файлы задач
```
