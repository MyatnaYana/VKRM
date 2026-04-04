"""
Навигатор агента по сценарной сети (граф переходов в Neo4j).

Объединяет эмоциональную и этическую модели для принятия решений.
На каждом шаге навигации:
  1. Вычисляется ΣΔE для всех доступных рёбер (эмоции + этика)
  2. Выбирается ребро с минимальным ΣΔE
  3. Применяются обновления из ребра (update_em_*, update_eth_*)
  4. Применяются TSK-правила обеих моделей (~20 эмоциональных + 4–10 этических)
"""

from typing import Dict, List, Tuple, Optional
from neo4j import GraphDatabase

from emotional_model import EmotionalModel, get_peak
from ethical_model import EthicalModel


class AgentNavigator:
    """
    Навигатор агента по сценарной сети.

    Использует комбинированный критерий ΣΔE = ΣΔE_emotional + ΣΔE_ethical
    для выбора оптимального ребра на каждом шаге.
    """

    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.emotional_model = EmotionalModel()
        self.ethical_model = EthicalModel()
        self.path: List[Tuple] = []

    def close(self):
        self.driver.close()

    # ── Инициализация агента ───────────────────────────────────────

    def init_from_node(self, start_id: str):
        """Загрузить начальные характеристики агента из узла Neo4j."""
        with self.driver.session() as session:
            rec = session.run(
                "MATCH (s:State {id: $id}) RETURN s", id=start_id
            ).single()
            if rec is None:
                raise ValueError(f"Узел {start_id} не найден в базе данных")
            node_props = dict(rec['s'])
            self.emotional_model.load_from_node(node_props)
            self.ethical_model.load_from_node(node_props)

    def set_custom_params(self, custom: dict):
        """
        Установить пользовательские параметры агента.
        Ключи вида emotion_* и ethic_* распределяются по моделям.
        """
        emotion_params = {k: v for k, v in custom.items() if k.startswith('emotion_')}
        ethic_params = {k: v for k, v in custom.items() if k.startswith('ethic_')}

        if emotion_params:
            self.emotional_model.set_values(emotion_params)
            print(f"  Загружено {len(emotion_params)} эмоциональных параметров")
        if ethic_params:
            self.ethical_model.set_values(ethic_params)
            print(f"  Загружено {len(ethic_params)} этических параметров")

    # ── Вычисление отклонений ──────────────────────────────────────

    def compute_total_deviation(self, edge_props: dict) -> Tuple[float, float, float]:
        """
        Вычислить комбинированный критерий ΣΔE = ΣΔE_em + ΣΔE_eth.
        Возвращает (total, emotional_part, ethical_part).
        """
        em_dev = self.emotional_model.compute_deviation(edge_props)
        eth_dev = self.ethical_model.compute_deviation(edge_props)
        return (round(em_dev + eth_dev, 3), round(em_dev, 3), round(eth_dev, 3))

    # ── Применение обновлений ──────────────────────────────────────

    def apply_all_updates(self, edge_props: dict, verbose: bool = False):
        """
        Применить все обновления после выбора ребра:
          1. Обновления из свойств ребра (update_em_*, update_eth_*)
          2. TSK-правила эмоциональной модели (~20 правил)
          3. TSK-правила этической модели (4–10 правил)
        """
        # Шаг 1: обновления из ребра
        self.emotional_model.apply_edge_updates(edge_props)
        self.ethical_model.apply_edge_updates(edge_props)

        # Шаг 2: TSK-правила эмоциональной модели
        em_deltas = self.emotional_model.apply_tsk_rules(verbose=verbose)
        if verbose and em_deltas:
            print(f"  Δ эмоций (TSK): {em_deltas}")

        # Шаг 3: TSK-правила этической модели
        eth_deltas = self.ethical_model.apply_tsk_rules(verbose=verbose)
        if verbose and eth_deltas:
            print(f"  Δ этики (TSK):  {eth_deltas}")

    # ── Получение состояния ────────────────────────────────────────

    def get_full_state(self) -> Dict[str, float]:
        """Получить полное состояние агента (эмоции + этика)."""
        state = {}
        state.update(self.emotional_model.get_all())
        state.update(self.ethical_model.get_all())
        return state

    def get_nonzero_state(self) -> Dict[str, float]:
        """Получить ненулевые характеристики."""
        state = {}
        state.update(self.emotional_model.get_nonzero())
        state.update(self.ethical_model.get_nonzero())
        return state

    # ── Основной цикл навигации ────────────────────────────────────

    def navigate(self, start_id: str = 'V0',
                 custom_params: dict = None,
                 verbose: bool = True) -> List[Tuple]:
        """
        Основной цикл навигации по сценарной сети.

        Алгоритм:
          1. Инициализация агента из узла или пользовательских параметров
          2. Цикл: получить рёбра → вычислить ΣΔE → выбрать лучшее →
             применить обновления + TSK правила → перейти
          3. Вывод пройденного пути и финального состояния

        Args:
            start_id: идентификатор начального узла
            custom_params: словарь пользовательских параметров (опционально)
            verbose: выводить подробный лог

        Returns:
            Список шагов [(from_node, edge_id, to_node, total_dev), ...]
        """
        # ── Инициализация ──
        self.init_from_node(start_id)
        if custom_params:
            self.set_custom_params(custom_params)

        current = start_id
        self.path = []

        if verbose:
            print(f"\n{'='*60}")
            print(f"Начальное состояние агента (узел {start_id}):")
            print(f"  Эмоции: {self.emotional_model.get_nonzero()}")
            print(f"  Этика:  {self.ethical_model.get_nonzero()}")
            print(f"{'='*60}")

        # ── Цикл навигации ──
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

                # Вычисляем отклонения для всех рёбер
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

                # Вывод всех кандидатов
                if verbose:
                    print(f"\n=== Узел {current}: {len(candidates)} исходящих рёбер ===")
                    for c in sorted(candidates, key=lambda x: x['edge_id']):
                        print(f"  {c['edge_id']} → {c['next_id']} : "
                              f"ΣΔE = {c['total_dev']} "
                              f"(эмоции: {c['em_dev']}, этика: {c['eth_dev']})")

                # Выбираем лучшее ребро (минимальный ΣΔE)
                best = min(candidates, key=lambda x: x['total_dev'])

                if verbose:
                    print(f"→ ВЫБРАНО: {best['edge_id']} → {best['next_id']} "
                          f"(ΣΔE = {best['total_dev']})")

                # Записываем шаг
                self.path.append((
                    current,
                    best['edge_id'],
                    best['next_id'],
                    best['total_dev']
                ))

                # Применяем обновления + TSK-правила
                self.apply_all_updates(best['props'], verbose=verbose)

                current = best['next_id']

        # ── Итоговый вывод ──
        if verbose:
            print(f"\n{'='*60}")
            print("ПРОЙДЕННЫЙ ПУТЬ:")
            for step in self.path:
                print(f"  {step[0]} --{step[1]}--> {step[2]} (ΣΔE = {step[3]})")

            path_str = " → ".join(
                [self.path[0][0]] + [s[2] for s in self.path])
            print(f"\nКраткий путь: {path_str}")

            print(f"\nФинальное состояние агента:")
            print(f"  Эмоции: {self.emotional_model.get_nonzero()}")
            print(f"  Этика:  {self.ethical_model.get_nonzero()}")
            print(f"{'='*60}")

        return self.path
