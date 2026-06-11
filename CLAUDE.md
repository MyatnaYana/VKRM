# CLAUDE.md

Этот файл — инструкция для Claude Code (claude.ai/code) по работе с данным репозиторием.

## Область работы

В этом репозитории Claude работает с **тремя ядровыми файлами** в корне:

```
agent_navigator.py    — навигатор агента по сценарной сети (Neo4j)
emotional_model.py    — эмоциональная подсистема (TSK, Geneva Emotion Wheel)
ethical_model.py      — этическая подсистема (TSK с иерархией приоритетов)
```

И **дополнительными файлами**, тоже в корне:

```
app.py                — Streamlit-приложение для пошаговой навигации
seed_scenario.py      — данные сценарной сети «Кредитный скоринг» (V0–V8, E1–E8),
                        профиль BASE_AGENT и CLI-загрузчик графа в Neo4j
test_scenario.py      — офлайн-тесты навигации (без подключения к Neo4j)
requirements.txt      — зависимости приложения (neo4j, streamlit, pyvis, pandas)
```

**Текущий сценарий:** агент — ИИ-помощник кредитного аналитика банка. Поступила заявка клиента с пограничным скоринговым рейтингом и признаками неполных данных в анкете. Дилемма: передать на углублённую проверку (этично, но эмоционально дискомфортно) или одобрить без проверки (комфортно, но неэтично). По завершении прогона приложение выдаёт отчёт о доверии клиенту; вердикты хранятся в свойстве `verdict` терминальных узлов.

Всё остальное в репозитории (`main.py`, `Lab_work/`, `Extra/`, `Everything/`, `Previos/`, `lib/`, `venv/`, CSV, `.dot`, PNG, `.docx` и т. п.) относится к **смежным/учебным работам** и Claude не должен ни читать, ни модифицировать эти файлы без явной просьбы. При планировании изменений ориентируемся только на пять файлов выше.

Цель работы — **улучшение** этих модулей: рефакторинг, добавление функций, расширение TSK-правил, оптимизация, повышение читаемости/надёжности, типизация, документация, тесты для них.

## Обзор моделей

Интеллектуальный агент перемещается по сценарной сети — графу состояний/переходов в **Neo4j**. Выбор действия — объединённый подход (`combined`, единственный реализованный; параметр `mode` в `step()`/`navigate()` сохранён для совместимости):

- вычисляются общее эмоциональное состояние `Sem` (`EmotionalModel.compute_sem()`) и итоговая этическая оценка `Seth` (`EthicalModel.compute_seth()`);
- барьер активации `β` (свойство ребра `barrier`, по умолчанию 1.0) — порог осуществимости: действие осуществимо, если `Sem + Seth > β`;
- допустимы рёбра, у которых выполняются ВСЕ неравенства условий перехода (`cond_*_le|_ge`, сравнение по пикам — `check_edge_conditions`) И преодолён барьер; среди них выбирается ребро с минимальной суммой отклонений `ΣΔE = ΣΔE_em + ΣΔE_eth`; при равенстве — `random.choice`;
- если ни одно ребро не проходит — процесс завершается.

**Узлы влияют на агента.** Попадая в новую ситуацию (узел), агент реагирует на её последствия: к его характеристикам применяются обновления `update_em_*`/`update_eth_*` из свойств ДОСТИГНУТОГО узла, после чего срабатывают TSK-правила обеих моделей (`apply_all_updates(edge_props, node_props=...)`). Рёбра тоже могут нести обновления, но в эталонном сценарии все обновления заданы на узлах.

**Топология сети «Кредитный скоринг»:** `V0 → {E1→V1, E2→V2}`, `V1 → {E3→V3, E4→V4, E5→V5}`, `V2 → {E6→V6, E7→V7, E8→V8}`. Эталонные пути: ответственный аналитик — V0→V1→V4, формалист — V0→V1→V3, милосердный — V0→V1→V5, низкоэтичный — V0→V2→V6.

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
- `EMOTION_TSK_RULES` — список из ~20 правил вида `{id, conditions, consequents, description}`. Условия сформулированы преимущественно в термах `medium`/`low` для эмоций, активных в сценарии: рабочий диапазон пиков агента ≈ 0.15…0.65, поэтому условия `high` (μ > 0 только при пике > 0.6) почти не активировались бы.
- `ALL_EMOTIONS` — канонический список 20 эмоций GEW (включает `compassion` — сострадание).
- `POSITIVE_EMOTIONS` / `NEGATIVE_EMOTIONS` — валентность эмоций для `compute_sem()` (`surprise` нейтральна).
- `EmotionalModel.compute_sem()` — общее эмоциональное состояние `Sem ∈ [0,1]` для режима барьеров.
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
- `ALL_ETHICS = ['responsibility','goodness','conscience','evil','honesty','justice','fairness']` (justice — справедливость, fairness — порядочность).
- `compute_seth()` — итоговая этическая оценка `Seth ∈ [0,1]` для режима барьеров.
- `ETHIC_TSK_RULES` — 10 правил с полем `priority`.
- Класс `EthicalModel` зеркалит `EmotionalModel` (включая `as_table()`), но в `apply_tsk_rules` правила сортируются по приоритету, активация умножается на `priority_weight`, и `last_activations: List[Tuple[rule_id, w, description, priority]]` хранит четвёртое поле — приоритет правила.

### `agent_navigator.py`

Класс `AgentNavigator(uri=None, user=None, password=None)` хранит `driver`, `EmotionalModel`, `EthicalModel`, `path`. При `uri=None` навигатор создаётся без подключения к Neo4j — это используется в офлайн-тестах (`test_scenario.py`), где рёбра подаются вручную через `build_candidates` + `select_and_apply`.

Поток одного шага — метод `step(current_id, verbose=False, mode='combined') -> StepResult | None`:

1. Cypher: `MATCH (current:State {id: $current})-[e:TRANSITION]->(next:State) RETURN e, next.id, e.id, next`. Если рёбер нет — возвращает `None`.
2. `build_candidates(edges)` — принимает кортежи `(edge_id, next_id, edge_props)` или `(edge_id, next_id, edge_props, next_props)`; для каждого ребра: `compute_total_deviation(edge_props)` (округление до 3 знаков), допустимость (`check_edge_conditions` — выполнение всех неравенств `≤`/`≥` по пикам), барьер `β` (свойство `barrier`, по умолчанию `DEFAULT_BARRIER = 1.0`) и свойства целевого узла `next_props`.
3. `select_and_apply(current_id, candidates, verbose, mode)` — выбор ребра (combined): осуществимы рёбра, у которых выполняются ВСЕ неравенства условий И `Sem + Seth > β`; среди них минимум `ΣΔE`; ничьи — `random.choice`; если осуществимых нет — `None` (процесс завершается).
4. Запись шага в `self.path`.
5. `apply_all_updates(edge_props, verbose, node_props)`:
   - обновления из ребра (если заданы) — `apply_edge_updates`;
   - **обновления из ДОСТИГНУТОГО узла** (`node_props` — реакция агента на новую ситуацию, сдвиг `Tri` по `update_em_*`/`update_eth_*`);
   - `EmotionalModel.apply_tsk_rules`, затем `EthicalModel.apply_tsk_rules`.
6. Возвращает `StepResult` (dataclass) со всеми кандидатами, выбранным ребром, разбивкой отклонений, дельтами и сработавшими правилами обеих моделей.

`navigate(start_id, agent_params, verbose=True, mode='combined')` — оригинальный API: вызывает `init_agent`, затем крутит `step` в цикле до `None`. Возвращает `self.path`.

`fetch_graph_topology() -> (nodes, edges)` — читает все узлы и рёбра графа для внешней визуализации (используется `app.py`).

`compute_deviation_details(edge_props)` возвращает покомпонентную разбивку для логов и `StepResult.deviation_details`.

**Публичный dataclass `StepResult`** содержит: `from_node`, `to_node`, `edge_id`, `total_dev`, `em_dev`, `eth_dev`, `candidates`, `tied`, `chosen`, `deviation_details`, `em_deltas`, `eth_deltas`, `em_activations`, `eth_activations`, а также `admissible` (рёбра, прошедшие проверку условий), `mode`, `sem`, `seth`.

### Контракт схемы Neo4j (на что опираются три модуля)

- Узлы: `(:State {id: 'V0' | ..., description: <текст ситуации>, verdict: <вердикт о доверии — опционально, у терминальных узлов>, update_em_<emotion>:Δ, update_eth_<ethic>:Δ})` — обновления узла применяются к агенту при ВХОДЕ в узел (реакция на ситуацию).
- Рёбра: `(:State)-[:TRANSITION {id, description, barrier: β, cond_em_<emotion>_le|_ge:[a,b,c], cond_eth_<ethic>_le|_ge:[a,b,c]}]->(:State)`; рёбра могут нести и собственные `update_*` (применяются до узловых), но в эталонном сценарии обновления заданы на узлах.
- Имена эмоций — из `ALL_EMOTIONS`; этик — из `ALL_ETHICS`.
- Эталонные данные сети — в `seed_scenario.py` (`NODES`, `EDGES`, `BASE_AGENT`); загрузка: `python seed_scenario.py`.

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
- **Сайдбар:** креды Neo4j (с подхватом из `st.secrets["neo4j"]`), выбор пресета профиля (`BASE_AGENT` из `seed_scenario.py`, `_preset_merciful`, `_preset_low_ethics`, `_preset_formalist`, `_preset_anxious`, пустой), слайдеры для пика `b` каждой из 20 эмоций и 7 этик с настраиваемой полушириной `δ` (Tri = `[b-δ, b, b+δ]`), кнопки «Подключить» и «Сброс», поле начального узла, флаг verbose-логирования в stdout.
- **Главная область:** кнопки `▶ Шаг` / `⏭ До конца` / экспорт прогона в JSON; визуализация графа Neo4j через `pyvis` с подсветкой текущего узла (красный) и пройденных рёбер (зелёные); таблицы кандидатов с признаком допустимости и барьером `β`, разбивка `ΣΔE`; метрики `Sem`/`Seth` в режиме барьеров; активные TSK-правила обеих моделей с весами `w`; таблицы текущего состояния агента (через `as_table()`); таблица пройденного пути; **отчёт о доверии клиенту** по завершении прогона (`_render_trust_report`: описание и `verdict` финального узла + итоговые `Sem`/`Seth`).
- **`st.session_state` ключи:** `nav` (AgentNavigator), `current_node`, `finished`, `agent_profile`, `history` (сериализованные `StepResult`), `topology` (`fetch_graph_topology_full()`), `last_step`, `connection_error`, `verbose_console`, `selection_mode`. Между ререндерами Streamlit состояние сохраняется здесь.
- **Auto-режим** ограничен `guard < 1000` итераций для защиты от бесконечного цикла на потенциальных циклических графах.

Расширяя `app.py`, **не дублируйте** алгоритмическую логику из ядровых модулей — добавляйте методы в эти модули и вызывайте оттуда.

## Соглашения по коду (только для трёх рабочих файлов)

- **Префиксы ключей** в словарях агента: `emotion_<name>` и `ethic_<name>`. На них опирается парсер в `AgentNavigator.init_agent`.
- **Формат значений**: `[a, b, c]` (Python list), `b` — пик. При копировании профилей всегда `copy.deepcopy` (значения — изменяемые списки).
- **Хелперы `Tri`** определены в `emotional_model.py` и переиспользуются в `ethical_model.py` через импорт; новые хелперы тоже размещаем там.
- **Условия рёбер**: `cond_em_<emotion>_le|_ge`, `cond_eth_<ethic>_le|_ge`.
- **Обновления характеристик**: `update_em_<emotion>` / `update_eth_<ethic>` (число — дельта сдвига всей тройки). Задаются на УЗЛАХ (реакция агента на ситуацию, применяются при входе) и опционально на рёбрах.
- **Иерархия приоритетов** в `ethical_model.py`: `priority ∈ {1: ВЫСШИЙ, 2: СРЕДНИЙ, 3: БАЗОВЫЙ}`, веса `{1:2.0, 2:1.5, 3:1.0}` — учитывать при добавлении правил.
- **Логи** — на русском, с разделителями `═` / `─` / `===`; при добавлении нового вывода сохранять стиль.
- **Типизация** — `typing.Dict/List/Tuple` уже используется; новые сигнатуры тоже типизировать.
- **Округление** — отклонения и дельты округляются до 3–4 знаков для читаемости логов; сохранять это поведение.
- **Защита от деления на ноль**: пороги `< 1e-6` уже применяются в `tri_membership`, `apply_tsk_rules`; при добавлении весов следовать тому же шаблону.

## Что НЕ делать

- **Не трогать ничего вне семи файлов** (`agent_navigator.py`, `emotional_model.py`, `ethical_model.py`, `app.py`, `seed_scenario.py`, `test_scenario.py`, `requirements.txt`). `main.py`, `Lab_work/`, `Extra/`, `Everything/`, `Previos/`, `lib/`, `venv/`, любые CSV/`.dot`/PNG/`.docx` — вне области работы.
- **Не ломать публичные имена**, на которые могут опираться внешние скрипты и `app.py`: `AgentNavigator`, `EmotionalModel`, `EthicalModel`, `StepResult`, `make_tri`, `shift_tri`, `get_peak`, `tri_membership`, `format_tri`, `ZERO_TRI`, `ALL_EMOTIONS`, `ALL_ETHICS`, `POSITIVE_EMOTIONS`, `NEGATIVE_EMOTIONS`, `EMOTION_TSK_RULES`, `ETHIC_TSK_RULES`, `EMOTION_TERMS`, `ETHIC_TERMS`, методы `step`, `navigate`, `init_agent`, `apply_all_updates`, `compute_total_deviation`, `compute_deviation_details`, `check_edge_conditions`, `build_candidates`, `select_and_apply`, `compute_sem`, `compute_seth`, `fetch_graph_topology`, `as_table`, атрибут `last_activations`; в `seed_scenario.py` — `NODES`, `EDGES`, `BASE_AGENT`, `load_scenario`. Расширять — можно, переименовывать без причины — нет.
- **Не тащить `streamlit`/`pyvis`/`pandas` в три ядровых модуля.** Эти зависимости разрешены ТОЛЬКО в `app.py`. Любая новая внешняя зависимость для ядровых модулей — через обсуждение.
- **Не использовать `dict(BASE_AGENT)`** для копирования профиля — нужен `copy.deepcopy` (значения — списки).
- **Не коммитить креды Neo4j** ни в один из пяти файлов. `agent_navigator.py` принимает `uri/user/password` параметрами; `app.py` берёт значения по умолчанию из `st.secrets["neo4j"]` (`uri`, `user`, `password`). Файл `.streamlit/secrets.toml` должен быть в `.gitignore`.

## Циклическая зависимость и порядок импорта

`ethical_model.py` импортирует из `emotional_model.py`. Обратной зависимости нет и быть не должно — общие хелперы живут в `emotional_model.py`. При рефакторинге, если хелперы вырастут в отдельную тему, можно вынести их в новый модуль (например, `tri_utils.py`), но это требует согласования.
