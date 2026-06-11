"""
Офлайн-тесты сценарной сети «Кредитный скоринг» (без подключения к Neo4j).

Проверяются:
  1. Краевые случаи хелперов треугольных ФП (плечевые термы, клиппинг).
  2. Навигация в режиме 'deviation' (фильтрация неравенств + мин. ΣΔE).
  3. Навигация в режиме 'barrier' (Sem + Seth > β).
  4. Завершение процесса, когда ни одно ребро не удовлетворяет условиям.

Запуск:
    python test_scenario.py
"""

import copy
from typing import Dict, List, Optional

from agent_navigator import AgentNavigator
from emotional_model import tri_membership, shift_tri, EMOTION_TERMS
from seed_scenario import BASE_AGENT, EDGES, NODES

# Свойства узлов по id — для передачи узловых обновлений (update_*)
_NODE_PROPS = {n['id']: n for n in NODES}


# ──────────────────────────────────────────────────────────────────────
#  Вспомогательная офлайн-навигация (данные подаются из seed_scenario)
# ──────────────────────────────────────────────────────────────────────

def _edges_from(node_id: str) -> List[tuple]:
    """Исходящие рёбра узла: (edge_id, next_id, props, next_props)."""
    out = []
    for e in EDGES:
        if e['from'] == node_id:
            props = {k: v for k, v in e.items() if k not in ('from', 'to')}
            out.append((e['id'], e['to'], props, _NODE_PROPS[e['to']]))
    return out


def run_offline(profile: Dict[str, List[float]], start: str = 'V0',
                mode: str = 'deviation', verbose: bool = False) -> List[str]:
    """Прогнать агента по сети без Neo4j. Возвращает список узлов пути."""
    nav = AgentNavigator()           # без подключения к БД
    nav.init_agent(copy.deepcopy(profile))
    current = start
    visited = [start]
    guard = 0
    while guard < 100:
        guard += 1
        edges = _edges_from(current)
        if not edges:
            break
        candidates = nav.build_candidates(edges)
        result = nav.select_and_apply(current, candidates,
                                      verbose=verbose, mode=mode)
        if result is None:
            break
        current = result.to_node
        visited.append(current)
    return visited


# ──────────────────────────────────────────────────────────────────────
#  Профили для тестов
# ──────────────────────────────────────────────────────────────────────

def _profile_low_ethics() -> Dict[str, List[float]]:
    """Формалист, ориентированный на план продаж: низкая этика."""
    p = copy.deepcopy(BASE_AGENT)
    p['ethic_responsibility'] = [0.2, 0.3, 0.4]
    p['ethic_goodness']       = [0.2, 0.3, 0.4]
    p['ethic_conscience']     = [0.2, 0.3, 0.4]
    p['ethic_fairness']       = [0.2, 0.3, 0.4]
    p['ethic_justice']        = [0.3, 0.4, 0.5]
    p['ethic_evil']           = [0.5, 0.6, 0.7]
    return p


def _profile_formalist() -> Dict[str, List[float]]:
    """Строгий формалист: высокая справедливость, низкое сострадание."""
    p = copy.deepcopy(BASE_AGENT)
    p['emotion_compassion'] = [0.2, 0.3, 0.4]
    p['emotion_pride']      = [0.4, 0.5, 0.6]
    return p


def _profile_merciful() -> Dict[str, List[float]]:
    """Милосердный агент: высокое сострадание и добро."""
    p = copy.deepcopy(BASE_AGENT)
    p['emotion_compassion'] = [0.6, 0.7, 0.8]
    p['ethic_goodness']     = [0.7, 0.8, 0.9]
    return p


# ──────────────────────────────────────────────────────────────────────
#  Тесты
# ──────────────────────────────────────────────────────────────────────

def test_tri_membership_shoulders():
    """Плечевые термы: μ = 1 на краях диапазона."""
    low = EMOTION_TERMS['low']
    high = EMOTION_TERMS['high']
    assert tri_membership(0.0, *low) == 1.0, "low(0) должно быть 1"
    assert tri_membership(1.0, *high) == 1.0, "high(1) должно быть 1"
    assert tri_membership(0.5, 0.2, 0.5, 0.8) == 1.0, "пик должен давать 1"
    assert tri_membership(0.9, *low) == 0.0
    assert tri_membership(0.1, *high) == 0.0
    print("✓ tri_membership: плечевые термы корректны")


def test_shift_tri_invariant():
    """После сдвига сохраняется инвариант a ≤ b ≤ c в [0, 1]."""
    for tri, delta in [([0.8, 0.9, 1.0], 0.5), ([0.1, 0.2, 0.3], -0.25),
                       ([0.0, 0.5, 1.0], 0.3), ([0.4, 0.5, 0.6], -1.0)]:
        a, b, c = shift_tri(tri, delta)
        assert 0.0 <= a <= b <= c <= 1.0, f"нарушен инвариант: {[a, b, c]}"
    print("✓ shift_tri: инвариант a ≤ b ≤ c сохраняется")


def test_base_agent_deviation():
    """Ответственный агент: V0 → V1 (проверка) → один из V3/V4/V5."""
    path = run_offline(BASE_AGENT, mode='deviation')
    print(f"  путь базового агента (deviation): {' → '.join(path)}")
    assert path[0] == 'V0'
    assert path[1] == 'V1', "ответственный агент обязан выбрать проверку (E1)"
    assert path[-1] in ('V3', 'V4', 'V5'), \
        "путь должен завершиться решением по клиенту (отказ / эмпатия / льгота)"
    print("✓ deviation: базовый агент идёт через проверку")


def test_low_ethics_deviation():
    """Низкоэтичный агент: V0 → V2 (одобрить не глядя) → один из V6/V7/V8."""
    path = run_offline(_profile_low_ethics(), mode='deviation')
    print(f"  путь низкоэтичного агента (deviation): {' → '.join(path)}")
    assert path[1] == 'V2', "низкоэтичный агент должен одобрить без проверки (E2)"
    assert path[-1] in ('V2', 'V6', 'V7', 'V8'), \
        "путь V2 завершается одним из последствий (или останавливается в V2)"
    print("✓ deviation: низкоэтичный агент уклоняется от проверки")


def test_formalist_deviation():
    """Формалист с низким состраданием: V1 → V3 (официальный отказ)."""
    path = run_offline(_profile_formalist(), mode='deviation')
    print(f"  путь формалиста (deviation): {' → '.join(path)}")
    assert path[1] == 'V1'
    print("✓ deviation: формалист идёт через проверку")


def test_base_agent_barrier():
    """Режим барьеров: этичный агент преодолевает высокий барьер E1."""
    path = run_offline(BASE_AGENT, mode='barrier')
    print(f"  путь базового агента (barrier): {' → '.join(path)}")
    assert path[1] == 'V1', "Sem + Seth этичного агента должно преодолеть β(E1)"
    print("✓ barrier: этичный агент преодолевает высокий барьер")


def test_low_ethics_barrier():
    """Режим барьеров: низкоэтичному агенту доступно только лёгкое действие."""
    path = run_offline(_profile_low_ethics(), mode='barrier')
    print(f"  путь низкоэтичного агента (barrier): {' → '.join(path)}")
    assert path[1] == 'V2', "низкая Seth не должна пропустить через β(E1)"
    print("✓ barrier: низкоэтичный агент идёт по пути наименьшего сопротивления")


def test_merciful_path():
    """Милосердный агент сразу предлагает льготную программу (E5 → V5)."""
    path = run_offline(_profile_merciful())
    print(f"  путь милосердного агента: {' → '.join(path)}")
    assert path == ['V0', 'V1', 'V5'], \
        "милосердный агент должен прийти к льготной программе"
    print("✓ милосердный агент достигает V5")


def test_node_updates_applied():
    """Узловые обновления применяются: реакция агента на ситуацию."""
    nav = AgentNavigator()
    nav.init_agent(copy.deepcopy(BASE_AGENT))
    fear_before = nav.emotional_model.get_peak('fear')
    resp_before = nav.ethical_model.get_peak('responsibility')
    result = nav.select_and_apply('V0', nav.build_candidates(_edges_from('V0')))
    assert result is not None and result.to_node == 'V1'
    # V1 несёт update_em_fear = +0.05 и update_eth_responsibility = +0.05;
    # TSK-вывод добавляет собственные сдвиги, поэтому проверяем минимум
    assert nav.emotional_model.get_peak('fear') >= fear_before + 0.05 - 1e-9, \
        "узловое обновление страха (V1) не применилось"
    assert nav.ethical_model.get_peak('responsibility') >= resp_before + 0.05 - 1e-9, \
        "узловое обновление ответственности (V1) не применилось"
    print("✓ узловые обновления характеристик применяются при входе в узел")


def test_combined_mode():
    """Объединённый режим: условия + барьер как осуществимость, мин. ΣΔE."""
    path = run_offline(BASE_AGENT, mode='combined')
    print(f"  путь базового агента (combined): {' → '.join(path)}")
    assert path[1] == 'V1', "этичный агент проходит и условия, и барьер E1"
    path_low = run_offline(_profile_low_ethics(), mode='combined')
    print(f"  путь низкоэтичного агента (combined): {' → '.join(path_low)}")
    assert path_low[1] == 'V2', "низкоэтичному агенту осуществимо только E2"
    print("✓ combined: барьер — осуществимость, ΣΔE — предпочтение")


def test_emotion_rules_activate():
    """Эмоциональные TSK-правила должны срабатывать на пути сценария."""
    nav = AgentNavigator()
    nav.init_agent(copy.deepcopy(BASE_AGENT))
    current = 'V0'
    total_activations = 0
    while True:
        edges = _edges_from(current)
        if not edges:
            break
        result = nav.select_and_apply(current, nav.build_candidates(edges))
        if result is None:
            break
        total_activations += len(result.em_activations)
        current = result.to_node
    print(f"  активаций эмоциональных правил на пути: {total_activations}")
    assert total_activations > 0, "эмоциональные TSK-правила не активируются"
    print("✓ TSK: эмоциональные правила активируются")


def test_termination_no_admissible():
    """Если ни одно ребро не удовлетворяет условиям — процесс завершается."""
    p = copy.deepcopy(BASE_AGENT)
    # Парализованный страхом агент: нарушает cond_em_fear_le у E1 и E2
    p['emotion_fear'] = [0.8, 0.9, 1.0]
    p['emotion_joy']  = [0.0, 0.1, 0.2]
    path = run_offline(p, mode='deviation')
    print(f"  путь «парализованного» агента: {' → '.join(path)}")
    assert path == ['V0'], "процесс должен завершиться в V0"
    print("✓ deviation: завершение при отсутствии допустимых рёбер")


if __name__ == '__main__':
    print('═' * 60)
    print('Офлайн-тесты сценарной сети «Кредитный скоринг»')
    print('═' * 60)
    test_tri_membership_shoulders()
    test_shift_tri_invariant()
    test_base_agent_deviation()
    test_low_ethics_deviation()
    test_formalist_deviation()
    test_base_agent_barrier()
    test_low_ethics_barrier()
    test_merciful_path()
    test_node_updates_applied()
    test_combined_mode()
    test_emotion_rules_activate()
    test_termination_no_admissible()
    print('─' * 60)
    print('Все тесты пройдены ✓')
