# Сервис ядра

Компании, филиалы, сотрудники, оргструктура и смены. Вокруг него живут
остальные: справочник, к которому ходят все, и владелец понятия «кто есть кто».

## Зависимости

| Пакет | Роль |
|---|---|
| [`mirea-contracts`](https://github.com/mireacrm/contracts-py) | сообщения и стабы gRPC |
| [`mireacrm-common`](https://github.com/mireacrm/py-common) | настройки, метрики, трасса, ошибки, база, события, gRPC |

Оба приезжают из своих репозиториев по версии из `pyproject.toml`.
Версию контрактов называет сервис, а не обвяз: два прямых URL одного
пакета pip считает конфликтом.

## Локально

```
pip install -e ".[dev]"
python -m pytest tests/unit -q
python -m pytest tests/integration -q   # нужен Postgres
docker build -t core-service .
```

Систему целиком поднимает [`mireacrm/deploy`](https://github.com/mireacrm/deploy).
