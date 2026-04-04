"""
Эмоциональная модель агента на основе нечёткого вывода Такаги–Сугено–Канга (TSK).

Модель использует Geneva Emotion Wheel (GEW) — 20 эмоциональных переменных.
На каждом шаге навигации применяется ~20 нечётких правил, обновляющих
эмоциональное состояние агента в зависимости от контекста перехода.

Каждая эмоция представлена треугольной функцией принадлежности Tri(a, b, c),
где b — пиковое значение (степень принадлежности = 1).
"""

from typing import Dict, List, Tuple


# ──────────────────────────────────────────────────────────────────────
#  Треугольная функция принадлежности
# ──────────────────────────────────────────────────────────────────────

def tri_membership(x: float, a: float, b: float, c: float) -> float:
    """
    Вычисляет степень принадлежности x к треугольному нечёткому множеству Tri(a, b, c).

    Tri(x; a, b, c) =
        0,              если x <= a или x >= c
        (x - a)/(b - a), если a < x <= b
        (c - x)/(c - b), если b < x < c
    """
    if x <= a or x >= c:
        return 0.0
    elif x <= b:
        return (x - a) / (b - a) if b != a else 1.0
    else:
        return (c - x) / (c - b) if c != b else 1.0


def get_peak(tri) -> float:
    """Возвращает пиковое значение (b) треугольной функции Tri(a, b, c)."""
    if isinstance(tri, (list, tuple)) and len(tri) == 3:
        return float(tri[1])
    return float(tri) if isinstance(tri, (int, float)) else 0.0


# ──────────────────────────────────────────────────────────────────────
#  Лингвистические термы для эмоций
# ──────────────────────────────────────────────────────────────────────

# Термы: Low / Medium / High — для каждой эмоциональной переменной
EMOTION_TERMS = {
    'low':    (0.0, 0.0, 0.4),
    'medium': (0.2, 0.5, 0.8),
    'high':   (0.6, 1.0, 1.0),
}


def fuzzify_level(value: float) -> Dict[str, float]:
    """Фаззификация числового значения эмоции в степени принадлежности к термам."""
    return {
        term: tri_membership(value, *params)
        for term, params in EMOTION_TERMS.items()
    }


# ──────────────────────────────────────────────────────────────────────
#  TSK правила для эмоциональной модели (~20 правил)
# ──────────────────────────────────────────────────────────────────────
#
#  Каждое правило:
#    conditions  — словарь {emotion_name: required_term}
#    consequents — словарь {emotion_name: (p0, p1)}
#                  где выход = p0 + p1 * текущее_значение_эмоции
#
#  Степень активации правила: w_i = min(μ_term(emotion) для всех условий)
#  Итоговое обновление:  Δe = (Σ w_i * y_i) / (Σ w_i)   (взвешенное среднее TSK)
# ──────────────────────────────────────────────────────────────────────

# Структура одного правила:
#   {
#     'id': str,
#     'conditions': {emotion_name: term_name, ...},
#     'consequents': {emotion_name: (p0, p1), ...},
#     'description': str
#   }

EMOTION_TSK_RULES: List[dict] = [
    # ── Правила для радости (joy) ──────────────────────────────────
    {
        'id': 'ER01',
        'conditions': {'joy': 'high', 'guilt': 'low'},
        'consequents': {'joy': (0.05, 1.0), 'pride': (0.03, 1.0)},
        'description': 'Высокая радость при низкой вине → радость и гордость растут'
    },
    {
        'id': 'ER02',
        'conditions': {'joy': 'high', 'fear': 'high'},
        'consequents': {'joy': (-0.1, 1.0), 'surprise': (0.05, 1.0)},
        'description': 'Радость + страх → радость снижается, удивление растёт'
    },
    {
        'id': 'ER03',
        'conditions': {'joy': 'low', 'sadness': 'high'},
        'consequents': {'joy': (-0.05, 1.0), 'hope': (-0.03, 1.0)},
        'description': 'Низкая радость при высокой грусти → обе снижаются'
    },
    {
        'id': 'ER04',
        'conditions': {'joy': 'medium', 'gratitude': 'high'},
        'consequents': {'joy': (0.08, 1.0), 'love': (0.04, 1.0)},
        'description': 'Умеренная радость + благодарность → радость и любовь растут'
    },

    # ── Правила для страха (fear) ──────────────────────────────────
    {
        'id': 'ER05',
        'conditions': {'fear': 'high', 'anger': 'low'},
        'consequents': {'fear': (0.05, 1.0), 'sadness': (0.04, 1.0)},
        'description': 'Сильный страх без гнева → страх и грусть растут'
    },
    {
        'id': 'ER06',
        'conditions': {'fear': 'high', 'anger': 'high'},
        'consequents': {'fear': (-0.05, 1.0), 'anger': (0.06, 1.0)},
        'description': 'Страх + гнев → страх уступает гневу'
    },
    {
        'id': 'ER07',
        'conditions': {'fear': 'low', 'calmness': 'high'},
        'consequents': {'fear': (-0.03, 1.0), 'calmness': (0.02, 1.0)},
        'description': 'Низкий страх + спокойствие → устойчивое спокойствие'
    },

    # ── Правила для грусти (sadness) ───────────────────────────────
    {
        'id': 'ER08',
        'conditions': {'sadness': 'high', 'sympathy': 'high'},
        'consequents': {'sadness': (-0.04, 1.0), 'sympathy': (0.03, 1.0)},
        'description': 'Грусть + симпатия → грусть облегчается'
    },
    {
        'id': 'ER09',
        'conditions': {'sadness': 'high', 'guilt': 'high'},
        'consequents': {'sadness': (0.06, 1.0), 'shame': (0.04, 1.0)},
        'description': 'Грусть + вина → усиление обоих, стыд растёт'
    },
    {
        'id': 'ER10',
        'conditions': {'sadness': 'medium', 'nostalgia': 'high'},
        'consequents': {'sadness': (0.02, 1.0), 'hope': (0.03, 1.0)},
        'description': 'Умеренная грусть + ностальгия → надежда растёт'
    },

    # ── Правила для гнева (anger) ──────────────────────────────────
    {
        'id': 'ER11',
        'conditions': {'anger': 'high', 'contempt': 'high'},
        'consequents': {'anger': (0.05, 1.0), 'disgust': (0.04, 1.0)},
        'description': 'Гнев + презрение → усиление негативных эмоций'
    },
    {
        'id': 'ER12',
        'conditions': {'anger': 'high', 'guilt': 'medium'},
        'consequents': {'anger': (-0.06, 1.0), 'guilt': (0.05, 1.0)},
        'description': 'Гнев + вина → гнев снижается, вина растёт'
    },

    # ── Правила для вины (guilt) ───────────────────────────────────
    {
        'id': 'ER13',
        'conditions': {'guilt': 'high', 'shame': 'high'},
        'consequents': {'guilt': (0.04, 1.0), 'sadness': (0.05, 1.0)},
        'description': 'Вина + стыд → усиление грусти'
    },
    {
        'id': 'ER14',
        'conditions': {'guilt': 'low', 'pride': 'high'},
        'consequents': {'guilt': (-0.02, 1.0), 'pride': (0.03, 1.0)},
        'description': 'Низкая вина + гордость → гордость укрепляется'
    },

    # ── Правила для гордости (pride) ───────────────────────────────
    {
        'id': 'ER15',
        'conditions': {'pride': 'high', 'admiration': 'medium'},
        'consequents': {'pride': (0.03, 1.0), 'joy': (0.04, 1.0)},
        'description': 'Гордость + восхищение → радость растёт'
    },

    # ── Правила для любви (love) ───────────────────────────────────
    {
        'id': 'ER16',
        'conditions': {'love': 'high', 'jealousy': 'high'},
        'consequents': {'love': (-0.04, 1.0), 'anger': (0.03, 1.0), 'fear': (0.02, 1.0)},
        'description': 'Любовь + ревность → любовь снижается, гнев и страх растут'
    },

    # ── Правила для надежды (hope) ─────────────────────────────────
    {
        'id': 'ER17',
        'conditions': {'hope': 'high', 'fear': 'low'},
        'consequents': {'hope': (0.04, 1.0), 'joy': (0.03, 1.0)},
        'description': 'Надежда без страха → надежда и радость растут'
    },
    {
        'id': 'ER18',
        'conditions': {'hope': 'low', 'sadness': 'high'},
        'consequents': {'hope': (-0.05, 1.0), 'sadness': (0.02, 1.0)},
        'description': 'Низкая надежда + грусть → отчаяние усиливается'
    },

    # ── Правила для интереса (interest) ────────────────────────────
    {
        'id': 'ER19',
        'conditions': {'interest': 'high', 'surprise': 'medium'},
        'consequents': {'interest': (0.03, 1.0), 'joy': (0.02, 1.0)},
        'description': 'Интерес + удивление → интерес и радость растут'
    },

    # ── Правила для спокойствия (calmness) ─────────────────────────
    {
        'id': 'ER20',
        'conditions': {'calmness': 'high', 'anger': 'low'},
        'consequents': {'calmness': (0.03, 1.0), 'fear': (-0.02, 1.0)},
        'description': 'Спокойствие без гнева → устойчивость растёт'
    },
]


# ──────────────────────────────────────────────────────────────────────
#  Класс эмоциональной модели
# ──────────────────────────────────────────────────────────────────────

# Полный список 20 эмоций GEW
ALL_EMOTIONS = [
    'joy', 'pride', 'admiration', 'love', 'hope',          # положительные
    'fear', 'sadness', 'shame', 'guilt', 'anger',          # отрицательные
    'disgust', 'envy', 'jealousy',                         # отрицательные (прод.)
    'surprise', 'calmness', 'interest', 'contempt',        # другие
    'nostalgia', 'sympathy', 'gratitude',                   # другие (прод.)
]


class EmotionalModel:
    """
    Эмоциональная подсистема агента.

    Хранит текущие значения 20 эмоций (пиковые значения треугольных функций).
    Применяет TSK-правила для обновления эмоций после каждого перехода.
    """

    def __init__(self):
        # Текущие пиковые значения эмоций (по умолчанию 0)
        self.state: Dict[str, float] = {e: 0.0 for e in ALL_EMOTIONS}
        self.rules = EMOTION_TSK_RULES

    def load_from_node(self, node_props: dict):
        """Загрузить эмоции из свойств узла Neo4j."""
        for key, value in node_props.items():
            if key.startswith('emotion_'):
                name = key[len('emotion_'):]
                self.state[name] = get_peak(value)

    def set_values(self, values: dict):
        """Установить конкретные значения эмоций."""
        for key, val in values.items():
            if key.startswith('emotion_'):
                name = key[len('emotion_'):]
                self.state[name] = float(val)

    def get_value(self, emotion_name: str) -> float:
        """Получить текущее значение эмоции."""
        return self.state.get(emotion_name, 0.0)

    def get_all(self) -> Dict[str, float]:
        """Получить все эмоции с префиксом emotion_."""
        return {f'emotion_{k}': v for k, v in self.state.items()}

    def get_nonzero(self) -> Dict[str, float]:
        """Получить только ненулевые эмоции."""
        return {f'emotion_{k}': round(v, 3)
                for k, v in self.state.items() if abs(v) > 1e-6}

    # ── TSK-вывод ──────────────────────────────────────────────────

    def _compute_rule_activation(self, rule: dict) -> float:
        """
        Вычислить степень активации правила (w_i).
        w_i = min(μ_term(emotion_value))  для всех условий правила.
        """
        activations = []
        for emotion_name, term_name in rule['conditions'].items():
            value = self.state.get(emotion_name, 0.0)
            term_params = EMOTION_TERMS[term_name]
            mu = tri_membership(value, *term_params)
            activations.append(mu)

        # t-norm = минимум (стандартная операция И)
        return min(activations) if activations else 0.0

    def _compute_rule_output(self, rule: dict, emotion_name: str) -> float:
        """
        Вычислить выход правила TSK для конкретной эмоции.
        y_i = p0 + p1 * current_value
        """
        p0, p1 = rule['consequents'][emotion_name]
        current = self.state.get(emotion_name, 0.0)
        return p0 + p1 * current

    def apply_tsk_rules(self, verbose: bool = False) -> Dict[str, float]:
        """
        Применить все TSK-правила и обновить эмоциональное состояние.

        Для каждой эмоции, затронутой правилами:
            new_value = (Σ w_i * y_i) / (Σ w_i)

        Возвращает словарь изменений (deltas).
        """
        # Собираем взвешенные выходы для каждой эмоции
        weighted_outputs: Dict[str, float] = {}
        weight_sums: Dict[str, float] = {}

        rule_log = []

        for rule in self.rules:
            w = self._compute_rule_activation(rule)
            if w < 1e-6:
                continue  # правило не активировано

            if verbose:
                rule_log.append(f"  {rule['id']}: w={w:.4f} — {rule['description']}")

            for emotion_name in rule['consequents']:
                y = self._compute_rule_output(rule, emotion_name)
                weighted_outputs[emotion_name] = weighted_outputs.get(emotion_name, 0.0) + w * y
                weight_sums[emotion_name] = weight_sums.get(emotion_name, 0.0) + w

        if verbose and rule_log:
            print("  [Эмоциональные TSK-правила]")
            for line in rule_log:
                print(line)

        # Вычисляем итоговые значения и дельты
        deltas = {}
        for emotion_name in weighted_outputs:
            if weight_sums[emotion_name] > 1e-6:
                new_value = weighted_outputs[emotion_name] / weight_sums[emotion_name]
                old_value = self.state.get(emotion_name, 0.0)
                delta = new_value - old_value
                deltas[emotion_name] = round(delta, 4)
                # Обновляем состояние, ограничивая [0, 1]
                self.state[emotion_name] = max(0.0, min(1.0, new_value))

        return deltas

    def apply_edge_updates(self, edge_props: dict):
        """
        Применить обновления из свойств ребра (update_em_*).
        Эти обновления дополняют TSK-правила.
        """
        for key, delta in edge_props.items():
            if key.startswith('update_em_'):
                emotion_name = key[len('update_em_'):]
                old = self.state.get(emotion_name, 0.0)
                self.state[emotion_name] = max(0.0, min(1.0, old + float(delta)))

    def compute_deviation(self, edge_props: dict) -> float:
        """
        Вычислить сумму отклонений ΣΔE для эмоциональных условий ребра.
        """
        total = 0.0
        for key, value in edge_props.items():
            if key.startswith('cond_em_') and (key.endswith('_le') or key.endswith('_ge')):
                emotion_name = key[8:-3]  # cond_em_joy_le → joy
                agent_val = self.state.get(emotion_name, 0.0)
                req_peak = get_peak(value)
                total += abs(req_peak - agent_val)
        return total

    def __repr__(self):
        nonzero = {k: round(v, 3) for k, v in self.state.items() if abs(v) > 1e-6}
        return f"EmotionalModel({nonzero})"
