"""
Эмоциональная модель агента на основе нечёткого вывода Такаги–Сугено–Канга (TSK).

Модель использует Geneva Emotion Wheel (GEW) — 20 эмоциональных переменных.
Каждая эмоция представлена треугольной функцией принадлежности Tri(a, b, c).

На каждом шаге навигации применяется ~20 нечётких правил, обновляющих
эмоциональное состояние агента.
"""

from typing import Dict, List, Tuple


# ──────────────────────────────────────────────────────────────────────
#  Треугольная функция принадлежности
# ──────────────────────────────────────────────────────────────────────

def tri_membership(x: float, a: float, b: float, c: float) -> float:
    """
    Вычисляет степень принадлежности x к нечёткому множеству Tri(a, b, c).

    Tri(x; a, b, c) =
        0,               если x < a или x > c
        1,               если x == b (включая вырожденные плечи a == b или b == c)
        (x - a)/(b - a), если a < x < b
        (c - x)/(c - b), если b < x < c

    Корректно обрабатывает «плечевые» термы с вырожденной стороной:
    для low = (0, 0, 0.4) точка x = 0 даёт μ = 1, для high = (0.6, 1, 1)
    точка x = 1 даёт μ = 1.
    """
    if x < a or x > c:
        return 0.0
    if abs(x - b) < 1e-9:
        return 1.0
    if x < b:
        return (x - a) / (b - a) if (b - a) > 1e-9 else 1.0
    return (c - x) / (c - b) if (c - b) > 1e-9 else 1.0


def get_peak(tri) -> float:
    """Возвращает пиковое значение (b) треугольной функции Tri(a, b, c)."""
    if isinstance(tri, (list, tuple)) and len(tri) == 3:
        return float(tri[1])
    return float(tri) if isinstance(tri, (int, float)) else 0.0


def make_tri(value) -> List[float]:
    """Нормализует значение в формат [a, b, c]."""
    if isinstance(value, (list, tuple)) and len(value) == 3:
        return [float(value[0]), float(value[1]), float(value[2])]
    v = float(value) if isinstance(value, (int, float)) else 0.0
    # Скалярное значение → симметричная тройка с шириной 0.1
    return [max(0.0, v - 0.1), v, min(1.0, v + 0.1)]


def shift_tri(tri: List[float], delta: float) -> List[float]:
    """
    Сдвигает всю треугольную функцию на delta: [a+δ, b+δ, c+δ].

    Каждая компонента ограничивается отрезком [0, 1]. Так как ограничение
    монотонно и все три точки сдвигаются на одну и ту же дельту,
    инвариант a ≤ b ≤ c сохраняется.
    """
    return [max(0.0, min(1.0, v + delta)) for v in tri]


def format_tri(tri: List[float]) -> str:
    """Форматирует тройку для вывода."""
    return f"Tri({tri[0]:.2f}, {tri[1]:.2f}, {tri[2]:.2f})"


# ──────────────────────────────────────────────────────────────────────
#  Лингвистические термы для эмоций
# ──────────────────────────────────────────────────────────────────────

EMOTION_TERMS = {
    'low':    (0.0, 0.0, 0.4),
    'medium': (0.2, 0.5, 0.8),
    'high':   (0.6, 1.0, 1.0),
}


# ──────────────────────────────────────────────────────────────────────
#  TSK правила для эмоциональной модели (~20 правил)
# ──────────────────────────────────────────────────────────────────────

# Правила сформулированы преимущественно в термах 'medium' и 'low'
# для эмоций, активных в сценарии (радость, гордость, страх, грусть,
# вина, стыд, гнев, отвращение, удивление, сострадание): рабочий
# диапазон пиков агента — примерно 0.15…0.65, поэтому условия 'high'
# (μ > 0 только при пике > 0.6) почти никогда не активировались бы.
EMOTION_TSK_RULES: List[dict] = [
    {'id': 'ER01', 'conditions': {'joy': 'medium', 'guilt': 'low'},
     'consequents': {'joy': (0.05, 1.0), 'pride': (0.03, 1.0)},
     'description': 'Радость при низкой вине → радость и гордость растут'},
    {'id': 'ER02', 'conditions': {'joy': 'medium', 'fear': 'medium'},
     'consequents': {'joy': (-0.05, 1.0), 'surprise': (0.04, 1.0)},
     'description': 'Радость + тревога → радость гасится, удивление растёт'},
    {'id': 'ER03', 'conditions': {'joy': 'low', 'sadness': 'medium'},
     'consequents': {'joy': (-0.03, 1.0), 'hope': (-0.03, 1.0)},
     'description': 'Низкая радость при грусти → надежда снижается'},
    {'id': 'ER04', 'conditions': {'joy': 'medium', 'compassion': 'medium'},
     'consequents': {'compassion': (0.04, 1.0), 'joy': (0.03, 1.0)},
     'description': 'Позитивный фон поддерживает сострадание'},
    {'id': 'ER05', 'conditions': {'fear': 'medium', 'anger': 'low'},
     'consequents': {'fear': (0.04, 1.0), 'sadness': (0.03, 1.0)},
     'description': 'Тревога без гнева → страх и грусть растут'},
    {'id': 'ER06', 'conditions': {'fear': 'high', 'anger': 'high'},
     'consequents': {'fear': (-0.05, 1.0), 'anger': (0.06, 1.0)},
     'description': 'Страх + гнев → страх уступает гневу'},
    {'id': 'ER07', 'conditions': {'fear': 'low', 'joy': 'medium'},
     'consequents': {'calmness': (0.04, 1.0), 'fear': (-0.02, 1.0)},
     'description': 'Низкий страх при радости → спокойствие растёт'},
    {'id': 'ER08', 'conditions': {'sadness': 'medium', 'compassion': 'medium'},
     'consequents': {'sadness': (-0.03, 1.0), 'compassion': (0.04, 1.0)},
     'description': 'Грусть + сострадание → грусть облегчается, эмпатия растёт'},
    {'id': 'ER09', 'conditions': {'sadness': 'medium', 'guilt': 'medium'},
     'consequents': {'sadness': (0.04, 1.0), 'shame': (0.03, 1.0)},
     'description': 'Грусть + вина → усиление обеих, стыд растёт'},
    {'id': 'ER10', 'conditions': {'sadness': 'high', 'hope': 'low'},
     'consequents': {'sadness': (0.03, 1.0), 'hope': (-0.04, 1.0)},
     'description': 'Сильная грусть без надежды → отчаяние усиливается'},
    {'id': 'ER11', 'conditions': {'anger': 'medium', 'disgust': 'medium'},
     'consequents': {'anger': (0.04, 1.0), 'contempt': (0.03, 1.0)},
     'description': 'Гнев + отвращение → презрение растёт'},
    {'id': 'ER12', 'conditions': {'anger': 'medium', 'guilt': 'medium'},
     'consequents': {'anger': (-0.05, 1.0), 'guilt': (0.04, 1.0)},
     'description': 'Гнев + вина → гнев снижается, вина растёт'},
    {'id': 'ER13', 'conditions': {'guilt': 'medium', 'shame': 'medium'},
     'consequents': {'guilt': (0.04, 1.0), 'sadness': (0.04, 1.0)},
     'description': 'Вина + стыд → усиление грусти'},
    {'id': 'ER14', 'conditions': {'guilt': 'low', 'pride': 'medium'},
     'consequents': {'guilt': (-0.02, 1.0), 'pride': (0.04, 1.0)},
     'description': 'Низкая вина + гордость → гордость укрепляется'},
    {'id': 'ER15', 'conditions': {'pride': 'medium', 'joy': 'medium'},
     'consequents': {'pride': (0.03, 1.0), 'joy': (0.03, 1.0)},
     'description': 'Гордость + радость взаимно усиливаются'},
    {'id': 'ER16', 'conditions': {'disgust': 'medium', 'sadness': 'medium'},
     'consequents': {'disgust': (0.04, 1.0), 'compassion': (-0.03, 1.0)},
     'description': 'Отвращение + грусть → эмпатия подавляется'},
    {'id': 'ER17', 'conditions': {'surprise': 'medium', 'fear': 'medium'},
     'consequents': {'surprise': (0.03, 1.0), 'interest': (0.03, 1.0)},
     'description': 'Удивление + тревога → настороженный интерес'},
    {'id': 'ER18', 'conditions': {'surprise': 'medium', 'joy': 'medium'},
     'consequents': {'interest': (0.04, 1.0), 'joy': (0.02, 1.0)},
     'description': 'Удивление + радость → интерес растёт'},
    {'id': 'ER19', 'conditions': {'compassion': 'high', 'sadness': 'medium'},
     'consequents': {'compassion': (0.03, 1.0), 'sadness': (-0.02, 1.0)},
     'description': 'Сильное сострадание смягчает грусть'},
    {'id': 'ER20', 'conditions': {'shame': 'medium', 'guilt': 'medium'},
     'consequents': {'shame': (0.03, 1.0), 'sadness': (0.03, 1.0)},
     'description': 'Стыд + вина → грусть растёт'},
]


# ──────────────────────────────────────────────────────────────────────
#  Полный список 20 эмоций GEW
# ──────────────────────────────────────────────────────────────────────

ALL_EMOTIONS = [
    'joy', 'pride', 'admiration', 'love', 'hope',
    'fear', 'sadness', 'shame', 'guilt', 'anger',
    'disgust', 'envy', 'jealousy',
    'surprise', 'calmness', 'interest', 'contempt',
    'nostalgia', 'compassion', 'gratitude',
]

# Валентность эмоций — используется при вычислении общего
# эмоционального состояния Sem (см. EmotionalModel.compute_sem).
# 'surprise' считается нейтральной и не входит ни в одну группу.
POSITIVE_EMOTIONS = [
    'joy', 'pride', 'admiration', 'love', 'hope',
    'calmness', 'interest', 'nostalgia', 'compassion', 'gratitude',
]
NEGATIVE_EMOTIONS = [
    'fear', 'sadness', 'shame', 'guilt', 'anger',
    'disgust', 'envy', 'jealousy', 'contempt',
]

# Нулевая тройка
ZERO_TRI = [0.0, 0.0, 0.0]


class EmotionalModel:
    """
    Эмоциональная подсистема агента.

    Хранит 20 эмоций как треугольные функции принадлежности Tri(a, b, c).
    Применяет TSK-правила для обновления эмоций после каждого перехода.
    """

    def __init__(self):
        self.state: Dict[str, List[float]] = {e: list(ZERO_TRI) for e in ALL_EMOTIONS}
        self.rules = EMOTION_TSK_RULES
        # Список (rule_id, w, description) — заполняется на каждом apply_tsk_rules.
        # Используется внешними интерфейсами (Streamlit и т. п.) для отображения
        # активированных правил без перехвата stdout.
        self.last_activations: List[Tuple[str, float, str]] = []

    def set_values(self, values: dict):
        """Установить значения эмоций из словаря {emotion_<n>: [a,b,c] или float}."""
        for key, val in values.items():
            if key.startswith('emotion_'):
                name = key[len('emotion_'):]
                self.state[name] = make_tri(val)

    def get_peak(self, emotion_name: str) -> float:
        """Получить пиковое значение (b) эмоции."""
        tri = self.state.get(emotion_name, ZERO_TRI)
        return tri[1]

    def get_all(self) -> Dict[str, List[float]]:
        """Получить все эмоции с префиксом emotion_."""
        return {f'emotion_{k}': v for k, v in self.state.items()}

    def get_nonzero(self) -> Dict[str, str]:
        """Получить ненулевые эмоции в формате Tri(a, b, c)."""
        return {f'emotion_{k}': format_tri(v)
                for k, v in self.state.items() if v[1] > 1e-6}

    def as_table(self) -> List[Tuple[str, float, float, float, float]]:
        """
        Табличное представление состояния для UI/логов.
        Возвращает список (name, a, b, c, peak) по всем 20 эмоциям
        в порядке `ALL_EMOTIONS`.
        """
        rows = []
        for name in ALL_EMOTIONS:
            tri = self.state.get(name, ZERO_TRI)
            rows.append((name, float(tri[0]), float(tri[1]), float(tri[2]), float(tri[1])))
        return rows

    # ── TSK-вывод ──────────────────────────────────────────────────

    def _compute_rule_activation(self, rule: dict) -> float:
        """w_i = min(μ_term(peak_value)) для всех условий правила."""
        activations = []
        for emotion_name, term_name in rule['conditions'].items():
            peak = self.get_peak(emotion_name)
            term_params = EMOTION_TERMS[term_name]
            mu = tri_membership(peak, *term_params)
            activations.append(mu)
        return min(activations) if activations else 0.0

    def _compute_rule_output(self, rule: dict, emotion_name: str) -> float:
        """y_i = p0 + p1 * current_peak"""
        p0, p1 = rule['consequents'][emotion_name]
        current = self.get_peak(emotion_name)
        return p0 + p1 * current

    def apply_tsk_rules(self, verbose: bool = False) -> Dict[str, float]:
        """
        Применить все TSK-правила и обновить эмоциональное состояние.
        Сдвигает всю тройку Tri(a, b, c) на вычисленную дельту.
        Возвращает словарь изменений (deltas по пиковым значениям).
        """
        weighted_outputs: Dict[str, float] = {}
        weight_sums: Dict[str, float] = {}
        rule_log = []
        self.last_activations = []

        for rule in self.rules:
            w = self._compute_rule_activation(rule)
            if w < 1e-6:
                continue
            self.last_activations.append((rule['id'], round(w, 4), rule['description']))
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

        deltas = {}
        for emotion_name in weighted_outputs:
            if weight_sums[emotion_name] > 1e-6:
                new_peak = weighted_outputs[emotion_name] / weight_sums[emotion_name]
                old_peak = self.get_peak(emotion_name)
                delta = new_peak - old_peak
                deltas[emotion_name] = round(delta, 4)
                self.state[emotion_name] = shift_tri(self.state[emotion_name], delta)

        return deltas

    def apply_edge_updates(self, edge_props: dict):
        """Применить обновления из ребра: сдвигает Tri(a,b,c) на delta."""
        for key, delta in edge_props.items():
            if key.startswith('update_em_'):
                emotion_name = key[len('update_em_'):]
                if emotion_name in self.state:
                    self.state[emotion_name] = shift_tri(
                        self.state[emotion_name], float(delta))

    def compute_sem(self) -> float:
        """
        Вычислить результирующее общее эмоциональное состояние Sem ∈ [0, 1].

        Sem = 0.5 + (mean_pos − mean_neg) / 2, где mean_pos и mean_neg —
        средние пиковые значения позитивных и негативных эмоций
        (списки POSITIVE_EMOTIONS / NEGATIVE_EMOTIONS).
        Значение 0.5 — нейтральное состояние; > 0.5 — преобладает
        позитивный фон, < 0.5 — негативный.

        Используется в режиме выбора действия по барьерам активации:
        Sem + Seth > β_i.
        """
        mean_pos = sum(self.get_peak(e) for e in POSITIVE_EMOTIONS) / len(POSITIVE_EMOTIONS)
        mean_neg = sum(self.get_peak(e) for e in NEGATIVE_EMOTIONS) / len(NEGATIVE_EMOTIONS)
        return round(0.5 + (mean_pos - mean_neg) / 2.0, 4)

    def compute_deviation(self, edge_props: dict) -> float:
        """Вычислить ΣΔE для эмоциональных условий ребра (по пикам)."""
        total = 0.0
        for key, value in edge_props.items():
            if key.startswith('cond_em_') and (key.endswith('_le') or key.endswith('_ge')):
                emotion_name = key[8:-3]
                agent_peak = self.get_peak(emotion_name)
                req_peak = get_peak(value)
                total += abs(req_peak - agent_peak)
        return total

    def __repr__(self):
        nonzero = {k: format_tri(v) for k, v in self.state.items() if v[1] > 1e-6}
        return f"EmotionalModel({nonzero})"