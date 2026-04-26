# CLAUDE.md

Этот файл — инструкция для Claude Code (claude.ai/code) по работе с данным репозиторием.

## Область работы

В этом репозитории Claude работает с **тремя ядровыми файлами** в корне:

```
agent_navigator.py    — навигатор агента по сценарной сети (Neo4j)
emotional_model.py    — эмоциональная подсистема (TSK, Geneva Emotion Wheel)
ethical_model.py      — этическая подсистема (TSK с иерархией приоритетов)
```

И **дополнительными файлами интерактивного интерфейса**, тоже в корне:

```
app.py                — Streamlit-приложение для пошаговой навигации
requirements.txt      — зависимости приложения (neo4j, streamlit, pyvis, pandas)
```

Всё остальное в репозитории (`main.py`, `Lab_work/`, `Extra/`, `Everything/`, `Previos/`, `lib/`, `venv/`, CSV, `.dot`, PNG, `.docx` и т. п.) относится к **смежным/учебным работам** и Claude не должен ни читать, ни модифицировать эти файлы без явной просьбы. При планировании изменений ориентируемся только на пять файлов выше.

Цель работы — **улучшение** этих модулей: рефакторинг, добавление функций, расширение TSK-правил, оптимизация, повышение читаемости/надёжности, типизация, документация, тесты для них.

## Обзор моделей

Интеллектуальный агент перемещается по сценарной сети — графу состояний/переходов в **Neo4j**. На каждом шаге выбирает исходящее ребро с минимальной суммой отклонений `ΣΔE = ΣΔE_em + ΣΔE_eth`; при равенстве — `random.choice` (см. цитату в `agent_navigator.py`).

Каждая характеристика агента — **треугольная функция принадлежности** `Tri(a, b, c)`, где `b` — пик. Подсистемы:

- **Эмоциональная** (`emotional_model.py`) — 20 эмоций (Geneva Emotion Wheel), ~20 TSK-правил, без приоритетов.
- **Этическая** (`ethical_model.py`) — 7 этических переменных, 10 TSK-правил с иерархией `priority ∈ {1,2,3}`; веса приоритетов `{1: 2.0, 2: 1.5, 3: 1.0}`.

## Технологический стек

- **Язык:** Python 3
- **БД:** Neo4j (драйвер `neo4j==6.0.2`, протокол `neo4j+s://` для Aura Cloud)
- **Ядровые модули** (`agent_navigator`, `emotional_model`, `ethical_model`): только стандартная библиотека (`random`, `typing`, `dataclasses`) и `neo4j`.
- **Streamlit-приложение** (`app.py`): дополнительно `streamlit`, `pyvis`, `pandas` (см. `requirements.txt`). Эти зависимости НЕ должны проникать в три ядровых модуля.

Запуск приложения:
```bash
pip install -r requirements.txt
streamlit run app.py
```

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
  - `as_table() -> List[Tuple[name, a, b, c, peak]]` — табличное представление для UI.
  - `_compute_rule_activation(rule)` = `min(μ_term(peak))`.
  - `_compute_rule_output(rule, name)` = `p0 + p1 * current_peak`.
  - `apply_tsk_rules(verbose)` — взвешенное среднее → сдвиг `Tri` на дельту. Дополнительно заполняет атрибут `last_activations: List[Tuple[rule_id, w, description]]` для внешних UI.
  - `apply_edge_updates(edge_props)` — `update_em_<emotion>` → `shift_tri`.
  - `compute_deviation(edge_props)` — `Σ |req_peak − agent_peak|` по `cond_em_*_le|_ge`.

### `ethical_model.py`

Импортирует хелперы из `emotional_model.py` (`tri_membership`, `get_peak`, `make_tri`, `shift_tri`, `format_tri`, `ZERO_TRI`).

- `ETHIC_TERMS` — те же `low/medium/high`.
- `ALL_ETHICS = ['responsibility','goodness','conscience','evil','honesty','fairness','integrity']`.
- `ETHIC_TSK_RULES` — 10 правил с полем `priority`.
- Класс `EthicalModel` зеркалит `EmotionalModel` (включая `as_table()`), но в `apply_tsk_rules` правила сортируются по приоритету, активация умножается на `priority_weight`, и `last_activations: List[Tuple[rule_id, w, description, priority]]` хранит четвёртое поле — приоритет правила.

### `agent_navigator.py`

Класс `AgentNavigator(uri, user, password)` хранит `driver`, `EmotionalModel`, `EthicalModel`, `path`. Поток одного шага вынесен в метод `step(current_id, verbose=False) -> StepResult | None`:

1. Cypher: `MATCH (current:State {id: $current})-[e:TRANSITION]->(next:State) RETURN e, next.id, e.id`. Если рёбер нет — возвращает `None`.
2. Для каждого ребра — `compute_total_deviation(edge_props)` = эмоциональное + этическое отклонения, округлённые до 3 знаков.
3. Выбирается ребро с минимальным `ΣΔE`; ничьи разрешаются `random.choice`.
4. Запись шага в `self.path`.
5. `apply_all_updates`:
   - `EmotionalModel.apply_edge_updates` + `EthicalModel.apply_edge_updates` (сдвиг `Tri` по `update_em_*`/`update_eth_*`).
   - `EmotionalModel.apply_tsk_rules`, затем `EthicalModel.apply_tsk_rules`.
6. Возвращает `StepResult` (dataclass) со всеми кандидатами, выбранным ребром, разбивкой отклонений, дельтами и сработавшими правилами обеих моделей.

`navigate(start_id, agent_params, verbose=True)` — оригинальный API: вызывает `init_agent`, затем крутит `step` в цикле до `None`. Возвращает `self.path`.

`fetch_graph_topology() -> (nodes, edges)` — читает все узлы и рёбра графа для внешней визуализации (используется `app.py`).

`compute_deviation_details(edge_props)` возвращает покомпонентную разбивку для логов и `StepResult.deviation_details`.

**Публичный dataclass `StepResult`** содержит: `from_node`, `to_node`, `edge_id`, `total_dev`, `em_dev`, `eth_dev`, `candidates`, `tied`, `chosen`, `deviation_details`, `em_deltas`, `eth_deltas`, `em_activations`, `eth_activations`.

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

### `app.py` — Streamlit-приложение

Тонкая обёртка над `AgentNavigator`. Не реализует никакой бизнес-логики — только UI. Все вычисления делегируются ядровым модулям через публичный API: `step()`, `as_table()`, `last_activations`, `fetch_graph_topology()`, `compute_deviation_details()`.

Структура:
- **Сайдбар:** креды Neo4j (с подхватом из `st.secrets["neo4j"]`), выбор пресета профиля (`BASE_AGENT`, `_preset_low_ethics`, `_preset_anxious`, пустой), слайдеры для пика `b` каждой из 20 эмоций и 7 этик с настраиваемой полушириной `δ` (Tri = `[b-δ, b, b+δ]`), кнопки «Подключить» и «Сброс», поле начального узла, флаг verbose-логирования в stdout.
- **Главная область:** кнопки `▶ Шаг` / `⏭ До конца` / экспорт прогона в JSON; визуализация графа Neo4j через `pyvis` с подсветкой текущего узла (красный) и пройденных рёбер (зелёные); таблицы кандидатов и разбивка `ΣΔE`; активные TSK-правила обеих моделей с весами `w`; таблицы текущего состояния агента (через `as_table()`); таблица пройденного пути.
- **`st.session_state` ключи:** `nav` (AgentNavigator), `current_node`, `finished`, `agent_profile`, `history` (сериализованные `StepResult`), `topology` (`fetch_graph_topology()`), `last_step`, `connection_error`, `verbose_console`. Между ререндерами Streamlit состояние сохраняется здесь.
- **Auto-режим** ограничен `guard < 1000` итераций для защиты от бесконечного цикла на потенциальных циклических графах.

Расширяя `app.py`, **не дублируйте** алгоритмическую логику из ядровых модулей — добавляйте методы в эти модули и вызывайте оттуда.

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

- **Не трогать ничего вне пяти файлов** (`agent_navigator.py`, `emotional_model.py`, `ethical_model.py`, `app.py`, `requirements.txt`). `main.py`, `Lab_work/`, `Extra/`, `Everything/`, `Previos/`, `lib/`, `venv/`, любые CSV/`.dot`/PNG/`.docx` — вне области работы.
- **Не ломать публичные имена**, на которые могут опираться внешние скрипты и `app.py`: `AgentNavigator`, `EmotionalModel`, `EthicalModel`, `StepResult`, `make_tri`, `shift_tri`, `get_peak`, `tri_membership`, `format_tri`, `ZERO_TRI`, `ALL_EMOTIONS`, `ALL_ETHICS`, `EMOTION_TSK_RULES`, `ETHIC_TSK_RULES`, `EMOTION_TERMS`, `ETHIC_TERMS`, методы `step`, `navigate`, `init_agent`, `apply_all_updates`, `compute_total_deviation`, `compute_deviation_details`, `fetch_graph_topology`, `as_table`, атрибут `last_activations`. Расширять — можно, переименовывать без причины — нет.
- **Не тащить `streamlit`/`pyvis`/`pandas` в три ядровых модуля.** Эти зависимости разрешены ТОЛЬКО в `app.py`. Любая новая внешняя зависимость для ядровых модулей — через обсуждение.
- **Не использовать `dict(BASE_AGENT)`** для копирования профиля — нужен `copy.deepcopy` (значения — списки).
- **Не коммитить креды Neo4j** ни в один из пяти файлов. `agent_navigator.py` принимает `uri/user/password` параметрами; `app.py` берёт значения по умолчанию из `st.secrets["neo4j"]` (`uri`, `user`, `password`). Файл `.streamlit/secrets.toml` должен быть в `.gitignore`.

## Циклическая зависимость и порядок импорта

`ethical_model.py` импортирует из `emotional_model.py`. Обратной зависимости нет и быть не должно — общие хелперы живут в `emotional_model.py`. При рефакторинге, если хелперы вырастут в отдельную тему, можно вынести их в новый модуль (например, `tri_utils.py`), но это требует согласования.
