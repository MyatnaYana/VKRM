"""
Главный модуль: запуск экспериментов лабораторной работы.

Исследование совместного влияния этических и эмоциональных моделей
на поведение интеллектуального агента.

Эксперименты:
  1. Базовый сценарий — высокоэтичный оптимист
  2. Эксперимент 1 — снижение этических ограничений
  3. Эксперимент 2 — усиление отрицательных эмоций
  4. Эксперимент 3 — исследование порога выбора (a_responsibility)
"""

from agent_navigator import AgentNavigator


# ──────────────────────────────────────────────────────────────────────
#  Подключение к Neo4j
# ──────────────────────────────────────────────────────────────────────

URI      = "neo4j+s://67842419.databases.neo4j.io"
USER     = "67842419"
PASSWORD = "1bH9PGphIXQXqVNAkFTFEFkwXffBcK3ypTqQHAikcYU"   


def run_base_experiment(nav: AgentNavigator):
    """
    Базовый эксперимент: высокоэтичный оптимист.
    Ожидаемый путь: V0 → E1 → V1 → E3 → V3
    """
    print("\n" + "═"*70)
    print("  БАЗОВЫЙ ЭКСПЕРИМЕНТ: Высокоэтичный оптимист")
    print("═"*70)
    path = nav.navigate('V0')
    return path


def run_experiment_1(nav: AgentNavigator):
    """
    Эксперимент 1: снижение этических ограничений.
    a_responsibility = 0.3, a_goodness = 0.3, a_conscience = 0.3,
    a_justice = 0.3, a_fairness = 0.3, a_evil = 0.6
    """
    print("\n" + "═"*70)
    print("  ЭКСПЕРИМЕНТ 1: Снижение этических ограничений")
    print("═"*70)

    low_ethics = {
        'ethic_responsibility': 0.3,
        'ethic_goodness':       0.3,
        'ethic_conscience':     0.3,
        'ethic_fairness':       0.3,
        'ethic_evil':           0.6,
        # honesty и integrity остаются из V0
    }
    path = nav.navigate('V0', custom_params=low_ethics)
    return path


def run_experiment_2(nav: AgentNavigator):
    """
    Эксперимент 2: усиление отрицательных эмоций.
    a_fear = 0.7, a_sadness = 0.7, a_guilt = 0.6, a_joy = 0.2
    Этические параметры — как в базовом эксперименте.
    """
    print("\n" + "═"*70)
    print("  ЭКСПЕРИМЕНТ 2: Усиление отрицательных эмоций")
    print("═"*70)

    negative_emotions = {
        'emotion_joy':     0.2,
        'emotion_fear':    0.7,
        'emotion_sadness': 0.7,
        'emotion_guilt':   0.6,
    }
    path = nav.navigate('V0', custom_params=negative_emotions)
    return path


def run_experiment_3(nav: AgentNavigator):
    """
    Эксперимент 3: исследование порога выбора.
    Последовательно уменьшаем a_responsibility с 0.8 до 0.3 с шагом 0.05.
    Ищем значение, при котором ΣΔ_E1 ≈ ΣΔ_E2 (разность меняет знак).
    """
    print("\n" + "═"*70)
    print("  ЭКСПЕРИМЕНТ 3: Исследование порога выбора (a_responsibility)")
    print("═"*70)

    print(f"\n{'a_resp':>8} | {'ΣΔ_E1':>8} | {'ΣΔ_E2':>8} | {'Разность':>10} | Выбранный путь")
    print("-" * 65)

    results = []
    resp_values = [round(0.8 - i * 0.05, 2) for i in range(11)]  # 0.8 → 0.3

    for resp in resp_values:
        # Инициализируем агента
        nav.init_from_node('V0')
        nav.set_custom_params({'ethic_responsibility': resp})

        # Получаем рёбра из V0
        with nav.driver.session() as session:
            result = session.run("""
                MATCH (current:State {id: 'V0'})-[e:TRANSITION]->(next:State)
                RETURN e, next.id AS next_id, e.id AS edge_id
            """)
            edges = list(result)

        # Вычисляем ΣΔE для каждого ребра
        deviations = {}
        for rec in edges:
            edge_props = dict(rec['e'])
            total_dev, em_dev, eth_dev = nav.compute_total_deviation(edge_props)
            deviations[rec['edge_id']] = total_dev

        # Ищем E1 и E2
        e1_dev = deviations.get('E1', None)
        e2_dev = deviations.get('E2', None)

        if e1_dev is not None and e2_dev is not None:
            diff = e2_dev - e1_dev
            chosen = 'V0→V1 (E1)' if e1_dev <= e2_dev else 'V0→V2 (E2)'
            print(f"{resp:>8.2f} | {e1_dev:>8.3f} | {e2_dev:>8.3f} | {diff:>+10.3f} | {chosen}")
            results.append((resp, e1_dev, e2_dev, diff, chosen))
        else:
            print(f"{resp:>8.2f} | {'N/A':>8} | {'N/A':>8} | {'N/A':>10} | рёбра не найдены")

    # Поиск точки смены знака
    print("\n" + "-" * 65)
    for i in range(1, len(results)):
        prev_diff = results[i-1][3]
        curr_diff = results[i][3]
        if prev_diff * curr_diff < 0:  # знак изменился
            print(f"  Смена знака между a_responsibility = {results[i-1][0]} и {results[i][0]}")
            threshold = (results[i-1][0] + results[i][0]) / 2
            print(f"  Приблизительный порог: a_responsibility ≈ {threshold:.3f}")
            break
    else:
        if results:
            if all(r[3] > 0 for r in results):
                print("  Путь через E1 остаётся оптимальным во всём диапазоне")
            elif all(r[3] < 0 for r in results):
                print("  Путь через E2 остаётся оптимальным во всём диапазоне")

    return results


# ──────────────────────────────────────────────────────────────────────
#  Запуск всех экспериментов
# ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    nav = AgentNavigator(URI, USER, PASSWORD)

    try:
        # Базовый эксперимент
        base_path = run_base_experiment(nav)

        # Эксперимент 1: низкая этика
        exp1_path = run_experiment_1(nav)

        # Эксперимент 2: отрицательные эмоции
        exp2_path = run_experiment_2(nav)

        # Эксперимент 3: поиск порога
        exp3_results = run_experiment_3(nav)

        # ── Итоговая сводка ──
        print("\n\n" + "═"*70)
        print("  ИТОГОВАЯ СВОДКА ЭКСПЕРИМЕНТОВ")
        print("═"*70)

        def path_str(p):
            if not p:
                return "пусто"
            return " → ".join([p[0][0]] + [s[2] for s in p])

        print(f"\n  Базовый:       {path_str(base_path)}")
        print(f"  Эксперимент 1: {path_str(exp1_path)}")
        print(f"  Эксперимент 2: {path_str(exp2_path)}")

        # Сравнение
        base_route = path_str(base_path)
        if path_str(exp1_path) != base_route:
            print(f"\n  ✦ Эксперимент 1 изменил маршрут (снижение этики)")
        if path_str(exp2_path) != base_route:
            print(f"  ✦ Эксперимент 2 изменил маршрут (отрицательные эмоции)")

    finally:
        nav.close()
        print("\nСоединение с Neo4j закрыто.")
