"""
Этическая модель агента на основе нечёткого вывода Такаги–Сугено–Канга (TSK).

Модель оперирует 7 этическими переменными с иерархией норм.
Каждая переменная — треугольная функция принадлежности Tri(a, b, c).

На каждом шаге применяется от 4 до 10 TSK-правил.
"""

from typing import Dict, List, Tuple
from emotional_model import (tri_membership, get_peak, make_tri, shift_tri,
                              format_tri, ZERO_TRI)


# ──────────────────────────────────────────────────────────────────────
#  Лингвистические термы для этических переменных
# ──────────────────────────────────────────────────────────────────────

ETHIC_TERMS = {
    'low':    (0.0, 0.0, 0.4),
    'medium': (0.2, 0.5, 0.8),
    'high':   (0.6, 1.0, 1.0),
}

ALL_ETHICS = [
    'responsibility', 'goodness', 'conscience', 'evil',
    'honesty', 'fairness', 'integrity',
]


# ──────────────────────────────────────────────────────────────────────
#  TSK правила для этической модели (4–10 правил)
# ──────────────────────────────────────────────────────────────────────

ETHIC_TSK_RULES: List[dict] = [
    {'id': 'ETH01', 'priority': 1,
     'conditions': {'evil': 'high', 'conscience': 'high'},
     'consequents': {'evil': (-0.15, 1.0), 'conscience': (0.05, 1.0)},
     'description': 'Высокое зло + совесть → зло резко снижается'},
    {'id': 'ETH02', 'priority': 1,
     'conditions': {'evil': 'high', 'conscience': 'low'},
     'consequents': {'evil': (0.05, 1.0), 'goodness': (-0.08, 1.0)},
     'description': 'Высокое зло без совести → зло растёт, добро падает'},
    {'id': 'ETH03', 'priority': 1,
     'conditions': {'evil': 'low', 'goodness': 'high'},
     'consequents': {'goodness': (0.03, 1.0), 'integrity': (0.02, 1.0)},
     'description': 'Низкое зло + добро → добро и порядочность укрепляются'},
    {'id': 'ETH04', 'priority': 2,
     'conditions': {'honesty': 'high', 'fairness': 'high'},
     'consequents': {'integrity': (0.06, 1.0), 'responsibility': (0.03, 1.0)},
     'description': 'Честность + справедливость → порядочность и ответственность растут'},
    {'id': 'ETH05', 'priority': 2,
     'conditions': {'honesty': 'low', 'fairness': 'low'},
     'consequents': {'integrity': (-0.08, 1.0), 'evil': (0.04, 1.0)},
     'description': 'Нечестность + несправедливость → порядочность падает, зло растёт'},
    {'id': 'ETH06', 'priority': 2,
     'conditions': {'honesty': 'high', 'evil': 'low'},
     'consequents': {'goodness': (0.04, 1.0), 'conscience': (0.02, 1.0)},
     'description': 'Честность при низком зле → добро и совесть растут'},
    {'id': 'ETH07', 'priority': 3,
     'conditions': {'responsibility': 'high', 'conscience': 'high'},
     'consequents': {'responsibility': (0.03, 1.0), 'goodness': (0.04, 1.0)},
     'description': 'Ответственность + совесть → добро укрепляется'},
    {'id': 'ETH08', 'priority': 3,
     'conditions': {'responsibility': 'low', 'goodness': 'low'},
     'consequents': {'conscience': (-0.05, 1.0), 'evil': (0.03, 1.0)},
     'description': 'Безответственность + отсутствие добра → совесть падает'},
    {'id': 'ETH09', 'priority': 3,
     'conditions': {'integrity': 'high', 'responsibility': 'medium'},
     'consequents': {'responsibility': (0.05, 1.0), 'fairness': (0.02, 1.0)},
     'description': 'Порядочность стимулирует рост ответственности'},
    {'id': 'ETH10', 'priority': 3,
     'conditions': {'conscience': 'medium', 'goodness': 'medium'},
     'consequents': {'conscience': (0.02, 1.0), 'honesty': (0.02, 1.0)},
     'description': 'Умеренная совесть и добро → постепенный рост обоих'},
]


class EthicalModel:
    """
    Этическая подсистема агента.

    Хранит 7 этических переменных как Tri(a, b, c).
    Применяет TSK-правила с учётом иерархии норм.
    """

    def __init__(self):
        self.state: Dict[str, List[float]] = {e: list(ZERO_TRI) for e in ALL_ETHICS}
        self.rules = ETHIC_TSK_RULES
        # Список (rule_id, w, description, priority) — заполняется на каждом
        # apply_tsk_rules. Используется внешними интерфейсами (Streamlit и т. п.)
        # для отображения активированных правил с иерархией приоритетов.
        self.last_activations: List[Tuple[str, float, str, int]] = []

    def set_values(self, values: dict):
        """Установить значения из словаря {ethic_<n>: [a,b,c] или float}."""
        for key, val in values.items():
            if key.startswith('ethic_'):
                name = key[len('ethic_'):]
                self.state[name] = make_tri(val)

    def get_peak(self, ethic_name: str) -> float:
        """Получить пиковое значение (b)."""
        tri = self.state.get(ethic_name, ZERO_TRI)
        return tri[1]

    def get_all(self) -> Dict[str, List[float]]:
        return {f'ethic_{k}': v for k, v in self.state.items()}

    def get_nonzero(self) -> Dict[str, str]:
        return {f'ethic_{k}': format_tri(v)
                for k, v in self.state.items() if v[1] > 1e-6}

    def as_table(self) -> List[Tuple[str, float, float, float, float]]:
        """
        Табличное представление состояния для UI/логов.
        Возвращает список (name, a, b, c, peak) по всем 7 этическим
        переменным в порядке `ALL_ETHICS`.
        """
        rows = []
        for name in ALL_ETHICS:
            tri = self.state.get(name, ZERO_TRI)
            rows.append((name, float(tri[0]), float(tri[1]), float(tri[2]), float(tri[1])))
        return rows

    # ── TSK-вывод с иерархией ──────────────────────────────────────

    def _compute_rule_activation(self, rule: dict) -> float:
        activations = []
        for ethic_name, term_name in rule['conditions'].items():
            peak = self.get_peak(ethic_name)
            term_params = ETHIC_TERMS[term_name]
            mu = tri_membership(peak, *term_params)
            activations.append(mu)
        return min(activations) if activations else 0.0

    def _compute_rule_output(self, rule: dict, ethic_name: str) -> float:
        p0, p1 = rule['consequents'][ethic_name]
        current = self.get_peak(ethic_name)
        return p0 + p1 * current

    def apply_tsk_rules(self, verbose: bool = False) -> Dict[str, float]:
        """Применить TSK-правила с иерархией. Сдвигает Tri(a,b,c)."""
        rules_by_priority = sorted(self.rules, key=lambda r: r.get('priority', 3))

        weighted_outputs: Dict[str, float] = {}
        weight_sums: Dict[str, float] = {}
        rule_log = []
        self.last_activations = []

        for rule in rules_by_priority:
            w = self._compute_rule_activation(rule)
            if w < 1e-6:
                continue
            priority = rule.get('priority', 3)
            priority_label = {1: 'ВЫСШИЙ', 2: 'СРЕДНИЙ', 3: 'БАЗОВЫЙ'}.get(priority, '?')
            self.last_activations.append(
                (rule['id'], round(w, 4), rule['description'], priority))
            if verbose:
                rule_log.append(
                    f"  {rule['id']} [{priority_label}]: w={w:.4f} — {rule['description']}")
            for ethic_name in rule['consequents']:
                y = self._compute_rule_output(rule, ethic_name)
                priority_weight = {1: 2.0, 2: 1.5, 3: 1.0}.get(
                    rule.get('priority', 3), 1.0)
                effective_w = w * priority_weight
                weighted_outputs[ethic_name] = (
                    weighted_outputs.get(ethic_name, 0.0) + effective_w * y)
                weight_sums[ethic_name] = (
                    weight_sums.get(ethic_name, 0.0) + effective_w)

        if verbose and rule_log:
            print("  [Этические TSK-правила]")
            for line in rule_log:
                print(line)

        all_deltas = {}
        for ethic_name in weighted_outputs:
            if weight_sums[ethic_name] > 1e-6:
                new_peak = weighted_outputs[ethic_name] / weight_sums[ethic_name]
                old_peak = self.get_peak(ethic_name)
                delta = new_peak - old_peak
                all_deltas[ethic_name] = round(delta, 4)
                self.state[ethic_name] = shift_tri(self.state[ethic_name], delta)

        return all_deltas

    def apply_edge_updates(self, edge_props: dict):
        """Применить обновления из ребра: сдвигает Tri(a,b,c) на delta."""
        for key, delta in edge_props.items():
            if key.startswith('update_eth_'):
                ethic_name = key[len('update_eth_'):]
                if ethic_name in self.state:
                    self.state[ethic_name] = shift_tri(
                        self.state[ethic_name], float(delta))

    def compute_deviation(self, edge_props: dict) -> float:
        """Вычислить ΣΔE для этических условий ребра (по пикам)."""
        total = 0.0
        for key, value in edge_props.items():
            if key.startswith('cond_eth_') and (key.endswith('_le') or key.endswith('_ge')):
                ethic_name = key[9:-3]
                agent_peak = self.get_peak(ethic_name)
                req_peak = get_peak(value)
                total += abs(req_peak - agent_peak)
        return total

    def __repr__(self):
        nonzero = {k: format_tri(v) for k, v in self.state.items() if v[1] > 1e-6}
        return f"EthicalModel({nonzero})"