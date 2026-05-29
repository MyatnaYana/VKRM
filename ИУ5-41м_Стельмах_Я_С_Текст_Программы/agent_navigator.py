"""
Навигатор агента по сценарной сети (граф переходов в Neo4j).

Агент приходит в сценарную сеть с предзагруженными моделями этики и эмоций.
Характеристики агента — треугольные функции принадлежности Tri(a, b, c).
Узлы сети описывают события, а не характеристики агента.
"""

import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from neo4j import GraphDatabase

from emotional_model import EmotionalModel, get_peak, make_tri
from ethical_model import EthicalModel


# ──────────────────────────────────────────────────────────────────────
#  Результат одного шага навигации
# ──────────────────────────────────────────────────────────────────────

@dataclass
class StepResult:
    """
    Результат одного шага навигации.

    Используется как для логирования в `navigate()`, так и для отрисовки
    в интерактивных интерфейсах (Streamlit и т. п.).
    """
    from_node: str
    to_node: str
    edge_id: str
    total_dev: float
    em_dev: float
    eth_dev: float
    candidates: List[dict]                      # все исходящие рёбра-кандидаты
    tied: List[dict]                            # рёбра с минимальным ΣΔE (для ничьи)
    chosen: dict                                # выбранное ребро (полный dict кандидата)
    deviation_details: List[Tuple[str, float, float, float]]
    em_deltas: Dict[str, float] = field(default_factory=dict)
    eth_deltas: Dict[str, float] = field(default_factory=dict)
    em_activations: List[Tuple[str, float, str]] = field(default_factory=list)
    eth_activations: List[Tuple[str, float, str, int]] = field(default_factory=list)


class AgentNavigator:
    """
    Навигатор агента по сценарной сети.

    Агент инициализируется ТОЛЬКО через явно переданные параметры.
    Все характеристики хранятся как Tri(a, b, c).
    """

    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.emotional_model = EmotionalModel()
        self.ethical_model = EthicalModel()
        self.path: List[Tuple] = []

    def close(self):
        self.driver.close()

    # ── Инициализация агента ───────────────────────────────────────

    def init_agent(self, agent_params: dict):
        """
        Инициализировать агента с заданными характеристиками.

        Args:
            agent_params: словарь характеристик агента.
                Значения — Tri(a, b, c) в виде [a, b, c]
                Ключи: 'emotion_<n>' и 'ethic_<n>'

        Пример:
            nav.init_agent({
                'emotion_joy':          [0.4, 0.5, 0.6],
                'ethic_responsibility': [0.7, 0.8, 0.9],
                ...
            })
        """
        self.emotional_model = EmotionalModel()
        self.ethical_model = EthicalModel()
        self.path = []

        emotion_count = 0
        ethic_count = 0

        for key, value in agent_params.items():
            if key.startswith('emotion_'):
                name = key[len('emotion_'):]
                self.emotional_model.state[name] = make_tri(value)
                emotion_count += 1
            elif key.startswith('ethic_'):
                name = key[len('ethic_'):]
                self.ethical_model.state[name] = make_tri(value)
                ethic_count += 1

        print(f"  Агент инициализирован: "
              f"{emotion_count} эмоций, {ethic_count} этических параметров")

    # ── Вычисление отклонений ──────────────────────────────────────

    def compute_total_deviation(self, edge_props: dict) -> Tuple[float, float, float]:
        """
        Вычислить ΣΔE = ΣΔE_em + ΣΔE_eth.
        Возвращает (total, emotional_part, ethical_part).
        """
        em_dev = self.emotional_model.compute_deviation(edge_props)
        eth_dev = self.ethical_model.compute_deviation(edge_props)
        return (round(em_dev + eth_dev, 3), round(em_dev, 3), round(eth_dev, 3))

    def compute_deviation_details(self, edge_props: dict) -> List[Tuple[str, float, float, float]]:
        """
        Подробная разбивка ΣΔE по каждому условию ребра.
        Возвращает список (param_name, req_peak, agent_peak, |deviation|).
        """
        details = []
        for key, value in edge_props.items():
            if key.startswith('cond_em_') and (key.endswith('_le') or key.endswith('_ge')):
                emotion_name = key[8:-3]
                agent_peak = self.emotional_model.get_peak(emotion_name)
                req_peak = get_peak(value)
                dev = abs(req_peak - agent_peak)
                details.append((emotion_name, req_peak, agent_peak, round(dev, 3)))
            elif key.startswith('cond_eth_') and (key.endswith('_le') or key.endswith('_ge')):
                ethic_name = key[9:-3]
                agent_peak = self.ethical_model.get_peak(ethic_name)
                req_peak = get_peak(value)
                dev = abs(req_peak - agent_peak)
                details.append((ethic_name, req_peak, agent_peak, round(dev, 3)))
        return details

    # ── Применение обновлений ──────────────────────────────────────

    def apply_all_updates(self, edge_props: dict, verbose: bool = False
                          ) -> Tuple[Dict[str, float], Dict[str, float]]:
        """
        Применить обновления после выбора ребра:
          1. Обновления из ребра (сдвиг Tri на delta)
          2. TSK-правила эмоциональной модели
          3. TSK-правила этической модели

        Возвращает (em_deltas, eth_deltas).
        """
        self.emotional_model.apply_edge_updates(edge_props)
        self.ethical_model.apply_edge_updates(edge_props)

        em_deltas = self.emotional_model.apply_tsk_rules(verbose=verbose)
        if verbose and em_deltas:
            print(f"  Δ эмоций (TSK): {em_deltas}")

        eth_deltas = self.ethical_model.apply_tsk_rules(verbose=verbose)
        if verbose and eth_deltas:
            print(f"  Δ этики (TSK):  {eth_deltas}")

        return em_deltas, eth_deltas

    # ── Получение состояния ────────────────────────────────────────

    def get_nonzero_state(self) -> Dict[str, str]:
        state = {}
        state.update(self.emotional_model.get_nonzero())
        state.update(self.ethical_model.get_nonzero())
        return state

    # ── Один шаг навигации (для интерактивных режимов) ─────────────

    def step(self, current_id: str, verbose: bool = False) -> Optional[StepResult]:
        """
        Выполнить ОДИН шаг навигации из узла `current_id`.

        Алгоритм:
          1. Cypher-запрос исходящих рёбер `(:State {id})-[:TRANSITION]->(:State)`.
          2. Для каждого ребра — `compute_total_deviation` и `compute_deviation_details`.
          3. Минимум по ΣΔE; ничьи разрешаются `random.choice`.
          4. Запись шага в `self.path`.
          5. `apply_all_updates` (рёберные сдвиги + TSK эмоций + TSK этики).

        Возвращает `StepResult` или `None`, если из узла нет исходящих рёбер.
        Не молчит при verbose=True — печатает кандидатов и выбор в том же
        стиле, что и `navigate()`.
        """
        with self.driver.session() as session:
            result = session.run("""
                MATCH (current:State {id: $current})-[e:TRANSITION]->(next:State)
                RETURN e, next.id AS next_id, e.id AS edge_id
            """, current=current_id)
            edges = list(result)

        if not edges:
            if verbose:
                print(f"\n  Узел {current_id}: нет исходящих рёбер → КОНЕЦ")
            return None

        candidates = []
        for rec in edges:
            edge_props = dict(rec['e'])
            total_dev, em_dev, eth_dev = self.compute_total_deviation(edge_props)
            candidates.append({
                'edge_id': rec['edge_id'],
                'next_id': rec['next_id'],
                'total_dev': total_dev,
                'em_dev': em_dev,
                'eth_dev': eth_dev,
                'props': edge_props,
            })

        if verbose:
            print(f"\n=== Узел {current_id}: {len(candidates)} исходящих рёбер ===")
            for c in sorted(candidates, key=lambda x: x['edge_id']):
                print(f"  {c['edge_id']} → {c['next_id']} : "
                      f"ΣΔE = {c['total_dev']} "
                      f"(эмоции: {c['em_dev']}, этика: {c['eth_dev']})")
                details = self.compute_deviation_details(c['props'])
                for param, req, agent, dev in details:
                    print(f"    {param}: |{req} − {agent}| = {dev}")

        min_dev = min(c['total_dev'] for c in candidates)
        tied = [c for c in candidates if abs(c['total_dev'] - min_dev) < 1e-6]

        if len(tied) > 1:
            chosen = random.choice(tied)
            if verbose:
                tied_ids = ', '.join(c['edge_id'] for c in tied)
                print(f"⚡ НИЧЬЯ: рёбра {tied_ids} имеют одинаковый ΣΔE = {min_dev}")
                print(f"  Выбор произвольный (согласно статье: "
                      f"'In case of equal values, the choice is made arbitrarily')")
                print(f"→ ВЫБРАНО: {chosen['edge_id']} → {chosen['next_id']} "
                      f"(ΣΔE = {chosen['total_dev']})")
        else:
            chosen = tied[0]
            if verbose:
                print(f"→ ВЫБРАНО: {chosen['edge_id']} → {chosen['next_id']} "
                      f"(ΣΔE = {chosen['total_dev']})")

        deviation_details = self.compute_deviation_details(chosen['props'])
        self.path.append((current_id, chosen['edge_id'],
                          chosen['next_id'], chosen['total_dev']))

        em_deltas, eth_deltas = self.apply_all_updates(chosen['props'], verbose=verbose)

        return StepResult(
            from_node=current_id,
            to_node=chosen['next_id'],
            edge_id=chosen['edge_id'],
            total_dev=chosen['total_dev'],
            em_dev=chosen['em_dev'],
            eth_dev=chosen['eth_dev'],
            candidates=candidates,
            tied=tied,
            chosen=chosen,
            deviation_details=deviation_details,
            em_deltas=em_deltas,
            eth_deltas=eth_deltas,
            em_activations=list(self.emotional_model.last_activations),
            eth_activations=list(self.ethical_model.last_activations),
        )

    # ── Основной цикл навигации ────────────────────────────────────

    def navigate(self, start_id: str, agent_params: dict,
                 verbose: bool = True) -> List[Tuple]:
        """
        Основной цикл навигации по сценарной сети.

        Args:
            start_id: идентификатор начального узла
            agent_params: характеристики агента (Tri(a,b,c) или float)
            verbose: подробный лог

        Returns:
            Список шагов [(from_node, edge_id, to_node, total_dev), ...]
        """
        self.init_agent(agent_params)
        current = start_id

        if verbose:
            print(f"\n{'='*60}")
            print(f"Начальное состояние агента (старт: узел {start_id}):")
            print(f"  Эмоции: {self.emotional_model.get_nonzero()}")
            print(f"  Этика:  {self.ethical_model.get_nonzero()}")
            print(f"{'='*60}")

        while True:
            result = self.step(current, verbose=verbose)
            if result is None:
                break
            current = result.to_node

        if verbose:
            print(f"\n{'='*60}")
            print("ПРОЙДЕННЫЙ ПУТЬ:")
            for s in self.path:
                print(f"  {s[0]} --{s[1]}--> {s[2]} (ΣΔE = {s[3]})")
            if self.path:
                path_str = " → ".join([self.path[0][0]] + [s[2] for s in self.path])
                print(f"\nКраткий путь: {path_str}")
            print(f"\nФинальное состояние агента:")
            print(f"  Эмоции: {self.emotional_model.get_nonzero()}")
            print(f"  Этика:  {self.ethical_model.get_nonzero()}")
            print(f"{'='*60}")

        return self.path

    # ── Чтение топологии графа (для визуализации) ──────────────────

    def fetch_graph_topology(self) -> Tuple[List[str], List[Tuple[str, str, str]]]:
        """
        Прочитать все узлы и рёбра графа сценарной сети.
        Возвращает (nodes, edges), где edges = [(from_id, to_id, edge_id), ...].
        Используется внешними инструментами визуализации.
        """
        with self.driver.session() as session:
            nodes_result = session.run("MATCH (n:State) RETURN n.id AS id")
            nodes = [rec['id'] for rec in nodes_result]

            edges_result = session.run("""
                MATCH (n:State)-[r:TRANSITION]->(m:State)
                RETURN n.id AS from_id, m.id AS to_id, r.id AS edge_id
            """)
            edges = [(rec['from_id'], rec['to_id'], rec['edge_id'])
                     for rec in edges_result]
        return nodes, edges

    def fetch_graph_topology_full(self
                                  ) -> Tuple[List[Dict[str, Any]],
                                             List[Dict[str, Any]]]:
        """
        Прочитать узлы и рёбра графа сценарной сети ВМЕСТЕ со всеми их свойствами.

        Возвращает (nodes, edges), где:
          nodes = [{'id': <str>, **all_node_properties}, ...]
          edges = [{'from': <str>, 'to': <str>, 'id': <str|None>,
                    **all_edge_properties}, ...]

        Используется внешним UI (например, `app.py`) для построения tooltip'ов
        с описанием узлов и рёбер. Не заменяет публичный
        `fetch_graph_topology()` — он продолжает работать в старом формате
        для обратной совместимости.
        """
        with self.driver.session() as session:
            nodes_result = session.run("MATCH (n:State) RETURN n")
            nodes: List[Dict[str, Any]] = []
            for rec in nodes_result:
                props = dict(rec['n'])
                # Гарантируем наличие 'id' даже если в БД он назван иначе.
                props.setdefault('id', props.get('id'))
                nodes.append(props)

            edges_result = session.run("""
                MATCH (n:State)-[r:TRANSITION]->(m:State)
                RETURN n.id AS from_id, m.id AS to_id, r AS rel
            """)
            edges: List[Dict[str, Any]] = []
            for rec in edges_result:
                props = dict(rec['rel'])
                edge: Dict[str, Any] = {
                    'from': rec['from_id'],
                    'to': rec['to_id'],
                    'id': props.pop('id', None),
                }
                edge.update(props)
                edges.append(edge)
        return nodes, edges
