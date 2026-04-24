# CLAUDE.md

Этот файл — инструкция для Claude Code (claude.ai/code) по работе с данным репозиторием.

## Область работы

В этом репозитории Claude работает **только с тремя файлами** в корне:

```
agent_navigator.py    — навигатор агента по сценарной сети (Neo4j)
emotional_model.py    — эмоциональная подсистема (TSK, Geneva Emotion Wheel)
ethical_model.py      — этическая подсистема (TSK с иерархией приоритетов)
```

Всё остальное в репозитории (`main.py`, `Lab_work/`, `Extra/`, `Everything/`, `Previos/`, `lib/`, `venv/`, CSV, `.dot`, PNG, `.docx` и т. п.) относится к **смежным/учебным работам** и Claude не должен ни читать, ни модифицировать эти файлы без явной просьбы. При планировании изменений ориентируемся только на три рабочих файла выше.

Цель работы — **улучшение** этих трёх модулей: рефакторинг, добавление функций, расширение TSK-правил, оптимизация, повышение читаемости/надёжности, типизация, документация, тесты для них.

## Обзор моделей

Интеллектуальный агент перемещается по сценарной сети — графу состояний/переходов в **Neo4j**. На каждом шаге выбирает исходящее ребро с минимальной суммой отклонений `ΣΔE = ΣΔE_em + ΣΔE_eth`; при равенстве — `random.choice` (см. цитату в `agent_navigator.py`).

Каждая характеристика агента — **треугольная функция принадлежности** `Tri(a, b, c)`, где `b` — пик. Подсистемы:

- **Эмоциональная** (`emotional_model.py`) — 20 эмоций (Geneva Emotion Wheel), ~20 TSK-правил, без приоритетов.
- **Этическая** (`ethical_model.py`) — 7 этических переменных, 10 TSK-правил с иерархией `priority ∈ {1,2,3}`; веса приоритетов `{1: 2.0, 2: 1.5, 3: 1.0}`.

## Технологический стек

- **Язык:** Python 3
- **БД:** Neo4j (драйвер `neo4j==6.0.2`, протокол `neo4j+s://` для Aura Cloud)
- Внешних зависимостей в трёх рабочих файлах больше нет — только стандартная библиотека (`random`, `typing`) и `neo4j` в `agent_navigator.py`.

## Архитектура трёх модулей

### `emotional_model.py`

Содержит:
- Хелперы для треугольных ФП: `tri_membership(x,a,b,c)`, `get_peak(tri)`, `make_tri(value)`, `shift_tri(tri,δ)`, `format_tri(tri)`, константа `ZERO_TRI = [0,0,0]`.
- Лингвистические термы `EMOTION_TERMS = {'low','medium','high'}`.
- `EMOTION_TSK_RULES` — список из ~20 правил вида `{id, conditions, consequents, description}`.
- `ALL_EMOTIONS` — канонический список 20 эмоций GEW.
- Класс `EmotionalModel` с методами:
  - `set_values(values)` — заполнить состояние из словаря с префиксом `emotion_`.
  - `get_peak(name)`, `get_all()`, `get_nonzero()`.
  - `_compute_rule_activation(rule)` = `min(μ_term(peak))`.
  - `_compute_rule_output(rule, name)` = `p0 + p1 * current_peak`.
  - `apply_tsk_rules(verbose)` — взвешенное среднее → сдвиг `Tri` на дельту.
  - `apply_edge_updates(edge_props)` — `update_em_<emotion>` → `shift_tri`.
  - `compute_deviation(edge_props)` — `Σ |req_peak − agent_peak|` по `cond_em_*_le|_ge`.

### `ethical_model.py`

Импортирует хелперы из `emotional_model.py` (`tri_membership`, `get_peak`, `make_tri`, `shift_tri`, `format_tri`, `ZERO_TRI`).

- `ETHIC_TERMS` — те же `low/medium/high`.
- `ALL_ETHICS = ['responsibility','goodness','conscience','evil','honesty','fairness','integrity']`.
- `ETHIC_TSK_RULES` — 10 правил с полем `priority`.
- Класс `EthicalModel` зеркалит `EmotionalModel`, но в `apply_tsk_rules` правила сортируются по приоритету и активация умножается на `priority_weight`.

### `agent_navigator.py`

Класс `AgentNavigator(uri, user, password)` хранит `driver`, `EmotionalModel`, `EthicalModel`, `path`. Поток одного шага:

1. `init_agent(agent_params)` — пересоздаёт обе подсистемы, парсит ключи по префиксам `emotion_` / `ethic_` через `make_tri`.
2. Cypher: `MATCH (current:State {id: $current})-[e:TRANSITION]->(next:State) RETURN e, next.id, e.id`.
3. Для каждого ребра — `compute_total_deviation(edge_props)` = эмоциональное + этическое отклонения, округлённые до 3 знаков.
4. Выбирается ребро с минимальным `ΣΔE`; ничьи разрешаются `random.choice`.
5. `apply_all_updates`:
   - `EmotionalModel.apply_edge_updates` + `EthicalModel.apply_edge_updates` (сдвиг `Tri` по `update_em_*`/`update_eth_*`).
   - `EmotionalModel.apply_tsk_rules`, затем `EthicalModel.apply_tsk_rules`.
6. Цикл до отсутствия исходящих рёбер.

`compute_deviation_details(edge_props)` возвращает покомпонентную разбивку для логов.

### Контракт схемы Neo4j (на что опираются три модуля)

- Узлы: `(:State {id: 'V0' | 'V1' | ...})`.
- Рёбра: `(:State)-[:TRANSITION {id, cond_em_<emotion>_le|_ge:[a,b,c], cond_eth_<ethic>_le|_ge:[a,b,c], update_em_<emotion>:Δ, update_eth_<ethic>:Δ}]->(:State)`.
- Имена эмоций — из `ALL_EMOTIONS`; этик — из `ALL_ETHICS`.

### Лингвистические термы

```
low    = (0.0, 0.0, 0.4)
medium = (0.2, 0.5, 0.8)
high   = (0.6, 1.0, 1.0)
```

Активация правила `w = min(μ_term(peak))`, следствие `y = p0 + p1 * current_peak`, выход — взвешенное среднее по правилам, затем сдвиг всей тройки `Tri` на полученную дельту.

## Соглашения по коду (только для трёх рабочих файлов)

- **Префиксы ключей** в словарях агента: `emotion_<name>` и `ethic_<name>`. На них опирается парсер в `AgentNavigator.init_agent`.
- **Формат значений**: `[a, b, c]` (Python list), `b` — пик. При копировании профилей всегда `copy.deepcopy` (значения — изменяемые списки).
- **Хелперы `Tri`** определены в `emotional_model.py` и переиспользуются в `ethical_model.py` через импорт; новые хелперы тоже размещаем там.
- **Условия рёбер**: `cond_em_<emotion>_le|_ge`, `cond_eth_<ethic>_le|_ge`.
- **Обновления рёбер**: `update_em_<emotion>` / `update_eth_<ethic>` (число — дельта сдвига всей тройки).
- **Иерархия приоритетов** в `ethical_model.py`: `priority ∈ {1: ВЫСШИЙ, 2: СРЕДНИЙ, 3: БАЗОВЫЙ}`, веса `{1:2.0, 2:1.5, 3:1.0}` — учитывать при добавлении правил.
- **Логи** — на русском, с разделителями `═` / `─` / `===`; при добавлении нового вывода сохранять стиль.
- **Типизация** — `typing.Dict/List/Tuple` уже используется; новые сигнатуры тоже типизировать.
- **Округление** — отклонения и дельты округляются до 3–4 знаков для читаемости логов; сохранять это поведение.
- **Защита от деления на ноль**: пороги `< 1e-6` уже применяются в `tri_membership`, `apply_tsk_rules`; при добавлении весов следовать тому же шаблону.

## Что НЕ делать

- **Не трогать ничего вне трёх файлов.** `main.py`, `Lab_work/`, `Extra/`, `Everything/`, `Previos/`, `lib/`, `venv/`, любые CSV/`.dot`/PNG/`.docx` — вне области работы.
- **Не ломать публичные имена**, на которые могут опираться внешние скрипты в репозитории: `AgentNavigator`, `EmotionalModel`, `EthicalModel`, `make_tri`, `shift_tri`, `get_peak`, `tri_membership`, `format_tri`, `ZERO_TRI`, `ALL_EMOTIONS`, `ALL_ETHICS`, `EMOTION_TSK_RULES`, `ETHIC_TSK_RULES`, `EMOTION_TERMS`, `ETHIC_TERMS`. Расширять — можно, переименовывать без причины — нет.
- **Не вводить новые внешние зависимости** без обсуждения. Стандартная библиотека и `neo4j` — достаточно для базового функционала.
- **Не использовать `dict(BASE_AGENT)`** для копирования профиля — нужен `copy.deepcopy` (значения — списки).
- **Не коммитить креды Neo4j** в эти три файла. `agent_navigator.py` принимает `uri/user/password` параметрами — так и оставлять.

## Циклическая зависимость и порядок импорта

`ethical_model.py` импортирует из `emotional_model.py`. Обратной зависимости нет и быть не должно — общие хелперы живут в `emotional_model.py`. При рефакторинге, если хелперы вырастут в отдельную тему, можно вынести их в новый модуль (например, `tri_utils.py`), но это требует согласования.
