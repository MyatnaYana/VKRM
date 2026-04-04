"""
Этическая модель агента на основе нечёткого вывода Такаги–Сугено–Канга (TSK).

Модель оперирует 7 этическими переменными с иерархией норм:
  1. Высший уровень: запрет причинения вреда (evil → min)
  2. Средний уровень: честность и справедливость
  3. Базовый уровень: индивидуальные предпочтения

На каждом шаге применяется от 4 до 10 TSK-правил, обновляющих
этическое состояние в зависимости от текущих значений и контекста.
"""

from typing import Dict, List
from emotional_model import tri_membership, get_peak


# ──────────────────────────────────────────────────────────────────────
#  Лингвистические термы для этических переменных
# ──────────────────────────────────────────────────────────────────────

ETHIC_TERMS = {
    'low':    (0.0, 0.0, 0.4),
    'medium': (0.2, 0.5, 0.8),
    'high':   (0.6, 1.0, 1.0),
}

# Полный список 7 этических переменных
ALL_ETHICS = [
    'responsibility',   # Ответственность
    'goodness',         # Добро / добродетель
    'conscience',       # Совесть
    'evil',             # Зло
    'honesty',          # Честность
    'fairness',         # Справедливость
    'integrity',        # Порядочность
]


def fuzzify_ethic(value: float) -> Dict[str, float]:
    """Фаззификация числового значения этической переменной."""
    return {
        term: tri_membership(value, *params)
        for term, params in ETHIC_TERMS.items()
    }


# ──────────────────────────────────────────────────────────────────────
#  TSK правила для этической модели (4–10 правил)
# ──────────────────────────────────────────────────────────────────────
#
#  Правила организованы по иерархии норм (деонтологический приоритет).
#  Высшие нормы имеют приоритет при конфликте.
#
#  Формат аналогичен эмоциональным правилам:
#    conditions  — {ethic_name: term}
#    consequents — {ethic_name: (p0, p1)}
#    priority    — уровень в иерархии (1 = высший, 3 = базовый)
# ──────────────────────────────────────────────────────────────────────

ETHIC_TSK_RULES: List[dict] = [
    # ═══ Высший уровень: запрет причинения вреда ═══════════════════
    {
        'id': 'ETH01',
        'priority': 1,
        'conditions': {'evil': 'high', 'conscience': 'high'},
        'consequents': {'evil': (-0.15, 1.0), 'conscience': (0.05, 1.0)},
        'description': 'Высокое зло + совесть → зло резко снижается'
    },
    {
        'id': 'ETH02',
        'priority': 1,
        'conditions': {'evil': 'high', 'conscience': 'low'},
        'consequents': {'evil': (0.05, 1.0), 'goodness': (-0.08, 1.0)},
        'description': 'Высокое зло без совести → зло растёт, добро падает'
    },
    {
        'id': 'ETH03',
        'priority': 1,
        'conditions': {'evil': 'low', 'goodness': 'high'},
        'consequents': {'goodness': (0.03, 1.0), 'integrity': (0.02, 1.0)},
        'description': 'Низкое зло + добро → добро и порядочность укрепляются'
    },

    # ═══ Средний уровень: честность и справедливость ═══════════════
    {
        'id': 'ETH04',
        'priority': 2,
        'conditions': {'honesty': 'high', 'fairness': 'high'},
        'consequents': {'integrity': (0.06, 1.0), 'responsibility': (0.03, 1.0)},
        'description': 'Честность + справедливость → порядочность и ответственность растут'
    },
    {
        'id': 'ETH05',
        'priority': 2,
        'conditions': {'honesty': 'low', 'fairness': 'low'},
        'consequents': {'integrity': (-0.08, 1.0), 'evil': (0.04, 1.0)},
        'description': 'Нечестность + несправедливость → порядочность падает, зло растёт'
    },
    {
        'id': 'ETH06',
        'priority': 2,
        'conditions': {'honesty': 'high', 'evil': 'low'},
        'consequents': {'goodness': (0.04, 1.0), 'conscience': (0.02, 1.0)},
        'description': 'Честность при низком зле → добро и совесть растут'
    },

    # ═══ Базовый уровень: индивидуальные предпочтения ══════════════
    {
        'id': 'ETH07',
        'priority': 3,
        'conditions': {'responsibility': 'high', 'conscience': 'high'},
        'consequents': {'responsibility': (0.03, 1.0), 'goodness': (0.04, 1.0)},
        'description': 'Ответственность + совесть → добро укрепляется'
    },
    {
        'id': 'ETH08',
        'priority': 3,
        'conditions': {'responsibility': 'low', 'goodness': 'low'},
        'consequents': {'conscience': (-0.05, 1.0), 'evil': (0.03, 1.0)},
        'description': 'Безответственность + отсутствие добра → совесть падает'
    },
    {
        'id': 'ETH09',
        'priority': 3,
        'conditions': {'integrity': 'high', 'responsibility': 'medium'},
        'consequents': {'responsibility': (0.05, 1.0), 'fairness': (0.02, 1.0)},
        'description': 'Порядочность стимулирует рост ответственности'
    },
    {
        'id': 'ETH10',
        'priority': 3,
        'conditions': {'conscience': 'medium', 'goodness': 'medium'},
        'consequents': {'conscience': (0.02, 1.0), 'honesty': (0.02, 1.0)},
        'description': 'Умеренная совесть и добро → постепенный рост обоих'
    },
]


# ──────────────────────────────────────────────────────────────────────
#  Класс этической модели
# ──────────────────────────────────────────────────────────────────────

class EthicalModel:
    """
    Этическая подсистема агента.

    Хранит 7 этических переменных и применяет TSK-правила
    с учётом иерархии норм (деонтологический приоритет).
    """

    def __init__(self):
        self.state: Dict[str, float] = {e: 0.0 for e in ALL_ETHICS}
        self.rules = ETHIC_TSK_RULES

    def load_from_node(self, node_props: dict):
        """Загрузить этические параметры из свойств узла Neo4j."""
        for key, value in node_props.items():
            if key.startswith('ethic_'):
                name = key[len('ethic_'):]
                self.state[name] = get_peak(value)

    def set_values(self, values: dict):
        """Установить конкретные значения этических параметров."""
        for key, val in values.items():
            if key.startswith('ethic_'):
                name = key[len('ethic_'):]
                self.state[name] = float(val)

    def get_value(self, ethic_name: str) -> float:
        return self.state.get(ethic_name, 0.0)

    def get_all(self) -> Dict[str, float]:
        return {f'ethic_{k}': v for k, v in self.state.items()}

    def get_nonzero(self) -> Dict[str, float]:
        return {f'ethic_{k}': round(v, 3)
                for k, v in self.state.items() if abs(v) > 1e-6}

    # ── TSK-вывод с иерархией ──────────────────────────────────────

    def _compute_rule_activation(self, rule: dict) -> float:
        """Степень активации правила: w_i = min(μ_term(value)) по всем условиям."""
        activations = []
        for ethic_name, term_name in rule['conditions'].items():
            value = self.state.get(ethic_name, 0.0)
            term_params = ETHIC_TERMS[term_name]
            mu = tri_membership(value, *term_params)
            activations.append(mu)
        return min(activations) if activations else 0.0

    def _compute_rule_output(self, rule: dict, ethic_name: str) -> float:
        """Выход TSK-правила: y_i = p0 + p1 * current_value."""
        p0, p1 = rule['consequents'][ethic_name]
        current = self.state.get(ethic_name, 0.0)
        return p0 + p1 * current

    def apply_tsk_rules(self, verbose: bool = False) -> Dict[str, float]:
        """
        Применить все этические TSK-правила с учётом иерархии.

        Правила высшего приоритета (priority=1) применяются первыми.
        Для каждого уровня: new_value = (Σ w_i * y_i) / (Σ w_i)

        Возвращает словарь изменений (deltas).
        """
        all_deltas = {}

        # Сортируем по приоритету: 1 (высший) → 3 (базовый)
        rules_by_priority = sorted(self.rules, key=lambda r: r.get('priority', 3))

        weighted_outputs: Dict[str, float] = {}
        weight_sums: Dict[str, float] = {}

        rule_log = []

        for rule in rules_by_priority:
            w = self._compute_rule_activation(rule)
            if w < 1e-6:
                continue

            priority_label = {1: 'ВЫСШИЙ', 2: 'СРЕДНИЙ', 3: 'БАЗОВЫЙ'}.get(
                rule.get('priority', 3), '?')
            if verbose:
                rule_log.append(
                    f"  {rule['id']} [{priority_label}]: w={w:.4f} — {rule['description']}")

            for ethic_name in rule['consequents']:
                y = self._compute_rule_output(rule, ethic_name)
                # Правила высшего приоритета получают больший вес
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

        # Вычисляем итоговые значения
        for ethic_name in weighted_outputs:
            if weight_sums[ethic_name] > 1e-6:
                new_value = weighted_outputs[ethic_name] / weight_sums[ethic_name]
                old_value = self.state.get(ethic_name, 0.0)
                delta = new_value - old_value
                all_deltas[ethic_name] = round(delta, 4)
                self.state[ethic_name] = max(0.0, min(1.0, new_value))

        return all_deltas

    def apply_edge_updates(self, edge_props: dict):
        """Применить обновления из свойств ребра (update_eth_*)."""
        for key, delta in edge_props.items():
            if key.startswith('update_eth_'):
                ethic_name = key[len('update_eth_'):]
                old = self.state.get(ethic_name, 0.0)
                self.state[ethic_name] = max(0.0, min(1.0, old + float(delta)))

    def compute_deviation(self, edge_props: dict) -> float:
        """Вычислить сумму отклонений ΣΔE для этических условий ребра."""
        total = 0.0
        for key, value in edge_props.items():
            if key.startswith('cond_eth_') and (key.endswith('_le') or key.endswith('_ge')):
                ethic_name = key[9:-3]  # cond_eth_responsibility_ge → responsibility
                agent_val = self.state.get(ethic_name, 0.0)
                req_peak = get_peak(value)
                total += abs(req_peak - agent_val)
        return total

    def __repr__(self):
        nonzero = {k: round(v, 3) for k, v in self.state.items() if abs(v) > 1e-6}
        return f"EthicalModel({nonzero})"
