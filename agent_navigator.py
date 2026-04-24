"""
Навигатор агента по сценарной сети (граф переходов в Neo4j).

Агент приходит в сценарную сеть с предзагруженными моделями этики и эмоций.
Характеристики агента — треугольные функции принадлежности Tri(a, b, c).
Узлы сети описывают события, а не характеристики агента.
"""

import random
from typing import Dict, List, Tuple
from neo4j import GraphDatabase

from emotional_model import EmotionalModel, get_peak, make_tri
from ethical_model import EthicalModel


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

    def apply_all_updates(self, edge_props: dict, verbose: bool = False):
        """
        Применить обновления после выбора ребра:
          1. Обновления из ребра (сдвиг Tri на delta)
          2. TSK-правила эмоциональной модели
          3. TSK-правила этической модели
        """
        self.emotional_model.apply_edge_updates(edge_props)
        self.ethical_model.apply_edge_updates(edge_props)

        em_deltas = self.emotional_model.apply_tsk_rules(verbose=verbose)
        if verbose and em_deltas:
            print(f"  Δ эмоций (TSK): {em_deltas}")

        eth_deltas = self.ethical_model.apply_tsk_rules(verbose=verbose)
        if verbose and eth_deltas:
            print(f"  Δ этики (TSK):  {eth_deltas}")

    # ── Получение состояния ────────────────────────────────────────

    def get_nonzero_state(self) -> Dict[str, str]:
        state = {}
        state.update(self.emotional_model.get_nonzero())
        state.update(self.ethical_model.get_nonzero())
        return state

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
        self.path = []

        if verbose:
            print(f"\n{'='*60}")
            print(f"Начальное состояние агента (старт: узел {start_id}):")
            print(f"  Эмоции: {self.emotional_model.get_nonzero()}")
            print(f"  Этика:  {self.ethical_model.get_nonzero()}")
            print(f"{'='*60}")

        while True:
            with self.driver.session() as session:
                result = session.run("""
                    MATCH (current:State {id: $current})-[e:TRANSITION]->(next:State)
                    RETURN e, next.id AS next_id, e.id AS edge_id
                """, current=current)
                edges = list(result)

                if not edges:
                    if verbose:
                        print(f"\n  Узел {current}: нет исходящих рёбер → КОНЕЦ")
                    break

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
                    print(f"\n=== Узел {current}: {len(candidates)} исходящих рёбер ===")
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
                    best = random.choice(tied)
                    if verbose:
                        tied_ids = ', '.join(c['edge_id'] for c in tied)
                        print(f"⚡ НИЧЬЯ: рёбра {tied_ids} имеют одинаковый ΣΔE = {min_dev}")
                        print(f"  Выбор произвольный (согласно статье: "
                              f"'In case of equal values, the choice is made arbitrarily')")
                        print(f"→ ВЫБРАНО: {best['edge_id']} → {best['next_id']} "
                              f"(ΣΔE = {best['total_dev']})")
                else:
                    best = tied[0]
                    if verbose:
                        print(f"→ ВЫБРАНО: {best['edge_id']} → {best['next_id']} "
                              f"(ΣΔE = {best['total_dev']})")

                self.path.append((current, best['edge_id'], best['next_id'], best['total_dev']))
                self.apply_all_updates(best['props'], verbose=verbose)
                current = best['next_id']

        if verbose:
            print(f"\n{'='*60}")
            print("ПРОЙДЕННЫЙ ПУТЬ:")
            for step in self.path:
                print(f"  {step[0]} --{step[1]}--> {step[2]} (ΣΔE = {step[3]})")
            path_str = " → ".join([self.path[0][0]] + [s[2] for s in self.path])
            print(f"\nКраткий путь: {path_str}")
            print(f"\nФинальное состояние агента:")
            print(f"  Эмоции: {self.emotional_model.get_nonzero()}")
            print(f"  Этика:  {self.ethical_model.get_nonzero()}")
            print(f"{'='*60}")

        return self.path