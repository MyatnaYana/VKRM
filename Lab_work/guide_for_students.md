# Руководство по выполнению лабораторной работы

## Структура проекта

Вы получаете 4 файла:

```
project/
├── emotional_model.py      ← готовый модуль, НЕ изменять
├── ethical_model.py         ← готовый модуль, НЕ изменять
├── agent_navigator.py       ← готовый модуль, НЕ изменять
└── main.py                  ← ВАШ РАБОЧИЙ ФАЙЛ (заполнить TODO)
```

Вся ваша работа ведётся **только в `main.py`**. Остальные файлы — это
фреймворк, реализующий эмоциональную модель (TSK), этическую модель (TSK)
и навигатор по сценарной сети.

---

## Шаг 0. Подключение к Neo4j

Откройте `main.py` и найдите строки подключения в начале файла:

```python
URI      = "neo4j+s://XXXXXXXX.databases.neo4j.io"
USER     = "XXXXXXXX"
PASSWORD = "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
```

**Замените** `XXXXXXXX` на реальные данные вашей базы Neo4j.

---

## Шаг 1. Базовый эксперимент (уже реализован)

Базовый эксперимент дан как **образец**. Изучите его — он показывает,
как устроен вызов навигации.

```python
BASE_AGENT = {
    'emotion_joy':         [0.4, 0.5, 0.6],   # Tri(a=0.4, b=0.5, c=0.6)
    'emotion_pride':       [0.3, 0.4, 0.5],
    ...
    'ethic_responsibility': [0.7, 0.8, 0.9],
    ...
}

def run_base_experiment(nav):
    path = nav.navigate('V0', BASE_AGENT)   # ← агент + начальный узел
    return path
```

Обратите внимание:
- Каждая характеристика агента — тройка `[a, b, c]` (треугольная функция
  принадлежности). Значение `b` — пик функции.
- `nav.navigate('V0', BASE_AGENT)` запускает навигацию из узла V0
  с указанным профилем агента.
- Агент **не загружается из узла** — узлы описывают события, а не агента.

**Запуск:**
```bash
python main.py base
```

**Ожидаемый результат:** путь `V0 → V1 → V3`.

Зафиксируйте в отчёте значения ΣΔE для каждого ребра.

---

## Шаг 2. Эксперимент 1: Снижение этических ограничений

Найдите в `main.py` функцию `run_experiment_1`. В ней два TODO.

### Что было (шаблон):

```python
def run_experiment_1(nav):
    ...
    low_ethics_agent = {}  # TODO

    path = None  # TODO: nav.navigate('V0', low_ethics_agent)
    return path
```

### Что нужно написать:

```python
import copy

def run_experiment_1(nav):
    ...
    # 1. Копируем базового агента (deepcopy, т.к. значения — списки)
    low_ethics_agent = copy.deepcopy(BASE_AGENT)

    # 2. Изменяем этические параметры
    low_ethics_agent['ethic_responsibility'] = [0.2, 0.3, 0.4]
    low_ethics_agent['ethic_goodness']       = [0.2, 0.3, 0.4]
    low_ethics_agent['ethic_conscience']     = [0.2, 0.3, 0.4]
    low_ethics_agent['ethic_justice']        = [0.2, 0.3, 0.4]
    low_ethics_agent['ethic_fairness']       = [0.2, 0.3, 0.4]
    low_ethics_agent['ethic_evil']           = [0.5, 0.6, 0.7]

    # 3. Запускаем навигацию
    path = nav.navigate('V0', low_ethics_agent)
    return path
```

**Почему `copy.deepcopy`?** Потому что значения в словаре — это списки
`[a, b, c]`. Обычный `dict(BASE_AGENT)` скопирует ссылки на те же
списки, и изменение `low_ethics_agent` повлияет на `BASE_AGENT`.

**Запуск:**
```bash
python main.py 1
```

**Что зафиксировать в отчёте:**
- Полученный путь (ожидается отличие от базового)
- Значения ΣΔE для рёбер E1 и E2 из узла V0
- Покомпонентную разбивку отклонений (выводится автоматически)

---

## Шаг 3. Эксперимент 2: Усиление отрицательных эмоций

### Что было:

```python
def run_experiment_2(nav):
    ...
    anxious_agent = {}  # TODO

    path = None  # TODO: nav.navigate('V0', anxious_agent)
    return path
```

### Что нужно написать:

```python
def run_experiment_2(nav):
    ...
    # 1. Копируем базового агента
    anxious_agent = copy.deepcopy(BASE_AGENT)

    # 2. Изменяем эмоциональные параметры (этика остаётся базовой!)
    anxious_agent['emotion_fear']    = [0.6, 0.7, 0.8]
    anxious_agent['emotion_sadness'] = [0.6, 0.7, 0.8]
    anxious_agent['emotion_guilt']   = [0.5, 0.6, 0.7]
    anxious_agent['emotion_joy']     = [0.1, 0.2, 0.3]

    # 3. Запускаем навигацию
    path = nav.navigate('V0', anxious_agent)
    return path
```

**Запуск:**
```bash
python main.py 2
```

**Что зафиксировать в отчёте:**
- Изменился ли путь и почему
- Какое эмоциональное ограничение дало наибольший вклад в ΣΔE

---

## Шаг 4. Эксперимент 3: Совместное изменение

### Что было:

```python
def run_experiment_3(nav):
    ...
    combined_agent = {}  # TODO

    path = None  # TODO: nav.navigate('V0', combined_agent)
    return path
```

### Что нужно написать:

```python
def run_experiment_3(nav):
    ...
    # 1. Копируем базового агента
    combined_agent = copy.deepcopy(BASE_AGENT)

    # 2. Изменяем этику (как в эксперименте 1)
    combined_agent['ethic_responsibility'] = [0.2, 0.3, 0.4]
    combined_agent['ethic_goodness']       = [0.2, 0.3, 0.4]
    combined_agent['ethic_conscience']     = [0.2, 0.3, 0.4]
    combined_agent['ethic_justice']        = [0.2, 0.3, 0.4]
    combined_agent['ethic_fairness']       = [0.2, 0.3, 0.4]
    combined_agent['ethic_evil']           = [0.5, 0.6, 0.7]

    # 3. Изменяем эмоции (как в эксперименте 2)
    combined_agent['emotion_fear']    = [0.6, 0.7, 0.8]
    combined_agent['emotion_sadness'] = [0.6, 0.7, 0.8]
    combined_agent['emotion_guilt']   = [0.5, 0.6, 0.7]
    combined_agent['emotion_joy']     = [0.1, 0.2, 0.3]

    # 4. Запускаем навигацию
    path = nav.navigate('V0', combined_agent)
    return path
```

**Запуск:**
```bash
python main.py 3
```

**Что зафиксировать в отчёте:**
- Совпадает ли путь с экспериментом 1, 2 или ни с одним?
- Является ли результат простой суммой эффектов экспериментов 1 и 2?

---

## Шаг 5. Эксперимент 4: Исследование порога выбора

Это самый сложный эксперимент — нужно написать цикл.

### Что было:

```python
def run_experiment_4(nav):
    ...
    # TODO: Перебирайте значения пика responsibility от 0.8 до 0.3

    pass  # TODO
```

### Что нужно написать:

```python
def run_experiment_4(nav):
    ...
    print(f"\n{'a_resp':>8} | {'ΣΔ_E1':>8} | {'ΣΔ_E2':>8} | "
          f"{'Разность':>10} | Выбранный путь")
    print("-" * 65)

    # 1. Список значений пика responsibility: от 0.8 до 0.3 с шагом 0.05
    resp_values = [round(0.8 - i * 0.05, 2) for i in range(11)]

    results = []

    for peak in resp_values:
        # 2. Создаём профиль агента с изменённой responsibility
        agent = copy.deepcopy(BASE_AGENT)
        agent['ethic_responsibility'] = [peak - 0.1, peak, peak + 0.1]

        # 3. Инициализируем агента (без запуска навигации)
        nav.init_agent(agent)

        # 4. Получаем рёбра из V0
        with nav.driver.session() as session:
            result = session.run("""
                MATCH (s:State {id: 'V0'})-[e:TRANSITION]->(t:State)
                RETURN e, t.id AS next_id, e.id AS edge_id
            """)
            edges = list(result)

        # 5. Вычисляем ΣΔE для каждого ребра
        deviations = {}
        for rec in edges:
            edge_props = dict(rec['e'])
            total, em, eth = nav.compute_total_deviation(edge_props)
            deviations[rec['edge_id']] = total

        # 6. Извлекаем E1 и E2
        e1 = deviations.get('E1', 0)
        e2 = deviations.get('E2', 0)
        diff = e2 - e1
        chosen = 'V0→V1 (E1)' if e1 <= e2 else 'V0→V2 (E2)'

        print(f"{peak:>8.2f} | {e1:>8.3f} | {e2:>8.3f} | "
              f"{diff:>+10.3f} | {chosen}")
        results.append((peak, e1, e2, diff))

    # 7. Ищем точку смены знака
    print("\n" + "-" * 65)
    for i in range(1, len(results)):
        if results[i-1][3] * results[i][3] < 0:
            threshold = (results[i-1][0] + results[i][0]) / 2
            print(f"  Порог переключения: a_responsibility ≈ {threshold:.3f}")
            break
```

**Запуск:**
```bash
python main.py 4
```

**Что зафиксировать в отчёте:**
- Заполненную таблицу с ΣΔE для каждого значения
- Значение порога переключения
- Объяснение, почему зависимость линейная (или нелинейная)

---

## Не забудьте добавить `import copy`

В начало файла `main.py`, после существующих импортов, добавьте:

```python
import copy
```

Эта строка нужна для `copy.deepcopy(BASE_AGENT)` в экспериментах 1–4.

---

## Итоговый запуск всех экспериментов

После выполнения всех TODO:

```bash
python main.py all
```

Это запустит все 5 экспериментов последовательно.
