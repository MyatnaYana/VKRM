"""
Навигатор агента по сценарной сети (граф переходов в Neo4j).

Агент приходит в сценарную сеть с предзагруженными моделями этики и эмоций.
Характеристики агента — треугольные функции принадлежности Tri(a, b, c).
Узлы сети описывают ситуации (события); попадая в новую ситуацию, агент
реагирует на её последствия: к его характеристикам применяются обновления
`update_em_*` / `update_eth_*`, заданные на узле, после чего срабатывают
TSK-правила обеих моделей. Рёбра описывают действия с условиями перехода
и барьерами активации (и могут нести собственные обновления).
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
    admissible: List[dict] = field(default_factory=list)  # рёбра, прошедшие проверку условий
    mode: str = 'combined'                      # режим выбора: 'combined'
    sem: float = 0.0                            # общее эмоциональное состояние (режим барьеров)
    seth: float = 0.0                           # этическая оценка (режим барьеров)


class AgentNavigator:
    """
    Навигатор агента по сценарной сети.

    Агент инициализируется ТОЛЬКО через явно переданные параметры.
    Все характеристики хранятся как Tri(a, b, c).
    """

    # Барьер активации по умолчанию для рёбер без свойства 'barrier'
    DEFAULT_BARRIER: float = 1.0

    def __init__(self, uri: Optional[str] = None, user: Optional[str] = None,
                 password: Optional[str] = None):
        # uri=None позволяет создать навигатор без подключения к Neo4j —
        # это используется в офлайн-тестах, где рёбра подаются вручную.
        self.driver = (GraphDatabase.driver(uri, auth=(user, password))
                       if uri else None)
        self.emotional_model = EmotionalModel()
        self.ethical_model = EthicalModel()
        self.path: List[Tuple] = []

    def close(self):
        if self.driver is not None:
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

    # ── Проверка условий перехода (неравенства ≤ / ≥) ──────────────

    def check_edge_conditions(self, edge_props: dict) -> Tuple[bool, List[str]]:
        """
        Проверить выполнение ВСЕХ условий перехода ребра.

        Условия задаются свойствами `cond_em_<имя>_le|_ge` и
        `cond_eth_<имя>_le|_ge`: суффикс `_le` требует, чтобы пик
        характеристики агента был ≤ пика ограничения, `_ge` — ≥.

        Согласно теоретическому описанию, агент сначала отбирает рёбра,
        для которых выполняются все неравенства, и лишь среди них
        минимизирует сумму отклонений ΣΔE.

        Возвращает (все_условия_выполнены, список_нарушенных_условий),
        где нарушенные условия описаны строками вида
        'fear: 0.45 > 0.3 (≤)'.
        """
        failed: List[str] = []
        eps = 1e-9
        for key, value in edge_props.items():
            if key.startswith('cond_em_') and (key.endswith('_le') or key.endswith('_ge')):
                name = key[8:-3]
                agent_peak = self.emotional_model.get_peak(name)
            elif key.startswith('cond_eth_') and (key.endswith('_le') or key.endswith('_ge')):
                name = key[9:-3]
                agent_peak = self.ethical_model.get_peak(name)
            else:
                continue
            req_peak = get_peak(value)
            if key.endswith('_le') and agent_peak > req_peak + eps:
                failed.append(f"{name}: {agent_peak:.3f} > {req_peak:.3f} (≤)")
            elif key.endswith('_ge') and agent_peak < req_peak - eps:
                failed.append(f"{name}: {agent_peak:.3f} < {req_peak:.3f} (≥)")
        return (len(failed) == 0, failed)

    # ── Применение обновлений ──────────────────────────────────────

    def apply_all_updates(self, edge_props: dict, verbose: bool = False,
                          node_props: Optional[dict] = None
                          ) -> Tuple[Dict[str, float], Dict[str, float]]:
        """
        Применить обновления после выбора ребра:
          1. Обновления из ребра (сдвиг Tri на delta) — если заданы
          2. Обновления из ДОСТИГНУТОГО узла: агент реагирует на новую
             ситуацию, получая изменения характеристик (update_em_*/update_eth_*
             в свойствах узла)
          3. TSK-правила эмоциональной модели
          4. TSK-правила этической модели

        Возвращает (em_deltas, eth_deltas).
        """
        self.emotional_model.apply_edge_updates(edge_props)
        self.ethical_model.apply_edge_updates(edge_props)

        # Реакция агента на ситуацию достигнутого узла
        if node_props:
            self.emotional_model.apply_edge_updates(node_props)
            self.ethical_model.apply_edge_updates(node_props)

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

    def build_candidates(self, edges: List[Tuple]) -> List[dict]:
        """
        Построить список рёбер-кандидатов из «сырых» рёбер.

        Args:
            edges: список (edge_id, next_id, edge_props) либо
                   (edge_id, next_id, edge_props, next_props), где
                   next_props — свойства целевого узла (включая его
                   обновления update_em_*/update_eth_*)

        Для каждого ребра вычисляются ΣΔE (с разбивкой на эмоциональную
        и этическую части), допустимость (выполнение всех неравенств
        условий перехода) и барьер активации β.
        """
        candidates = []
        for item in edges:
            edge_id, next_id, edge_props = item[0], item[1], item[2]
            next_props = item[3] if len(item) > 3 else {}
            total_dev, em_dev, eth_dev = self.compute_total_deviation(edge_props)
            admissible, failed = self.check_edge_conditions(edge_props)
            candidates.append({
                'edge_id': edge_id,
                'next_id': next_id,
                'total_dev': total_dev,
                'em_dev': em_dev,
                'eth_dev': eth_dev,
                'admissible': admissible,
                'failed_conditions': failed,
                'barrier': float(edge_props.get('barrier', self.DEFAULT_BARRIER)),
                'props': edge_props,
                'next_props': next_props,
            })
        return candidates

    def select_and_apply(self, current_id: str, candidates: List[dict],
                         verbose: bool = False,
                         mode: str = 'combined') -> Optional[StepResult]:
        """
        Выбрать ребро из кандидатов, применить обновления и вернуть StepResult.

        Режим 'combined' (единственный):
          Барьер выступает порогом осуществимости (хватает ли агенту
          «ресурса» Sem + Seth на действие), а сумма отклонений —
          мерой предпочтения. Допустимы рёбра, у которых выполняются
          ВСЕ неравенства условий И преодолён барьер (Sem + Seth > β);
          среди них выбирается минимальная ΣΔE; ничьи разрешаются
          произвольно. Если таких рёбер нет — процесс завершается.
        """
        sem = self.emotional_model.compute_sem()
        seth = self.ethical_model.compute_seth()

        if verbose:
            print(f"\n=== Узел {current_id}: {len(candidates)} исходящих рёбер ===")
            print(f"  Sem = {sem}, Seth = {seth}, Sem + Seth = {round(sem + seth, 4)}")
            for c in sorted(candidates, key=lambda x: x['edge_id']):
                status = "✓ допустимо" if c['admissible'] else "✗ НЕДОПУСТИМО"
                print(f"  {c['edge_id']} → {c['next_id']} : "
                      f"ΣΔE = {c['total_dev']} "
                      f"(эмоции: {c['em_dev']}, этика: {c['eth_dev']}), "
                      f"β = {c['barrier']} [{status}]")
                for cond in c['failed_conditions']:
                    print(f"    нарушено: {cond}")
                details = self.compute_deviation_details(c['props'])
                for param, req, agent, dev in details:
                    print(f"    {param}: |{req} − {agent}| = {dev}")

        # Осуществимость: выполнены все неравенства И преодолён барьер
        feasible = [c for c in candidates
                    if c['admissible'] and sem + seth > c['barrier']]
        if not feasible:
            if verbose:
                print(f"  Узел {current_id}: ни одно ребро не проходит "
                      f"одновременно по условиям и барьерам → КОНЕЦ")
            return None
        min_dev = min(c['total_dev'] for c in feasible)
        tied = [c for c in feasible if abs(c['total_dev'] - min_dev) < 1e-6]

        if len(tied) > 1:
            chosen = random.choice(tied)
            if verbose:
                tied_ids = ', '.join(c['edge_id'] for c in tied)
                print(f"⚡ НИЧЬЯ: рёбра {tied_ids} равнозначны — "
                      f"выбор произвольный (согласно описанию: «в случае "
                      f"равенства выбор осуществляется произвольно»)")
        else:
            chosen = tied[0]

        if verbose:
            print(f"→ ВЫБРАНО: {chosen['edge_id']} → {chosen['next_id']} "
                  f"(ΣΔE = {chosen['total_dev']}, β = {chosen['barrier']})")

        deviation_details = self.compute_deviation_details(chosen['props'])
        self.path.append((current_id, chosen['edge_id'],
                          chosen['next_id'], chosen['total_dev']))

        em_deltas, eth_deltas = self.apply_all_updates(
            chosen['props'], verbose=verbose,
            node_props=chosen.get('next_props'))

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
            admissible=[c for c in candidates if c['admissible']],
            mode=mode,
            sem=sem,
            seth=seth,
        )

    def step(self, current_id: str, verbose: bool = False,
             mode: str = 'combined') -> Optional[StepResult]:
        """
        Выполнить ОДИН шаг навигации из узла `current_id`.

        Алгоритм:
          1. Cypher-запрос исходящих рёбер `(:State {id})-[:TRANSITION]->(:State)`.
          2. `build_candidates` — ΣΔE, допустимость, барьеры β.
          3. `select_and_apply` — выбор ребра в режиме 'combined':
             выполнение всех неравенств условий И Sem + Seth > β,
             затем минимальная ΣΔE.

        Возвращает `StepResult` или `None`, если из узла нет исходящих рёбер
        либо ни одно ребро не проходит по условиям/барьерам.
        """
        with self.driver.session() as session:
            result = session.run("""
                MATCH (current:State {id: $current})-[e:TRANSITION]->(next:State)
                RETURN e, next.id AS next_id, e.id AS edge_id, next
            """, current=current_id)
            edges = [(rec['edge_id'], rec['next_id'], dict(rec['e']),
                      dict(rec['next']))
                     for rec in result]

        if not edges:
            if verbose:
                print(f"\n  Узел {current_id}: нет исходящих рёбер → КОНЕЦ")
            return None

        candidates = self.build_candidates(edges)
        return self.select_and_apply(current_id, candidates,
                                     verbose=verbose, mode=mode)

    # ── Основной цикл навигации ────────────────────────────────────

    def navigate(self, start_id: str, agent_params: dict,
                 verbose: bool = True, mode: str = 'combined') -> List[Tuple]:
        """
        Основной цикл навигации по сценарной сети.

        Args:
            start_id: идентификатор начального узла
            agent_params: характеристики агента (Tri(a,b,c) или float)
            verbose: подробный лог
            mode: режим выбора ребра (всегда 'combined': все неравенства
                  условий И Sem + Seth > β, затем минимальная ΣΔE)

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
            result = self.step(current, verbose=verbose, mode=mode)
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