"""
Лабораторная работа:
Исследование совместного влияния этических и эмоциональных моделей
на поведение интеллектуального агента.

ЗАДАНИЕ: Заполните блоки TODO для каждого эксперимента.

Запуск:
    python main.py base    — базовый эксперимент
    python main.py 1       — эксперимент 1
    python main.py 2       — эксперимент 2
    python main.py 3       — эксперимент 3
    python main.py all     — все эксперименты
"""

import sys
from agent_navigator import AgentNavigator
import copy

# ──────────────────────────────────────────────────────────────────────
#  Подключение к Neo4j (замените на свои данные)
# ──────────────────────────────────────────────────────────────────────

URI = "ХХХХХХХХХХХ"
USER = "ХХХХХХХХХХХ"
PASSWORD = "ХХХХХХХХХХ"


# ──────────────────────────────────────────────────────────────────────
#  Профиль базового агента: высокоэтичный оптимист (из статьи, Table 2)
#
#  Каждая характеристика — треугольная функция принадлежности Tri(a, b, c),
#  где b — пиковое значение (степень принадлежности = 1),
#  a и c — левое и правое основания.
# ──────────────────────────────────────────────────────────────────────

BASE_AGENT = {
    # Эмоции: Tri(a, b, c)
    'emotion_joy':         [0.4, 0.5, 0.6],
    'emotion_pride':       [0.3, 0.4, 0.5],
    'emotion_sadness':     [0.3, 0.4, 0.5],
    'emotion_fear':        [0.3, 0.4, 0.5],
    'emotion_shame':       [0.2, 0.3, 0.4],
    'emotion_guilt':       [0.2, 0.3, 0.4],
    'emotion_anger':       [0.2, 0.3, 0.4],
    'emotion_disgust':     [0.3, 0.4, 0.5],
    'emotion_surprise':    [0.2, 0.3, 0.4],
    'emotion_compassion':  [0.4, 0.5, 0.6],

    # Этика: Tri(a, b, c)
    'ethic_responsibility': [0.7, 0.8, 0.9],
    'ethic_goodness':       [0.6, 0.7, 0.8],
    'ethic_conscience':     [0.6, 0.7, 0.8],
    'ethic_evil':           [0.2, 0.3, 0.4],
    'ethic_honesty':        [0.6, 0.7, 0.8],
    'ethic_justice':        [0.6, 0.7, 0.8],
    'ethic_fairness':       [0.6, 0.7, 0.8],
}


# ══════════════════════════════════════════════════════════════════════
#  БАЗОВЫЙ ЭКСПЕРИМЕНТ
# ══════════════════════════════════════════════════════════════════════

def run_base_experiment(nav: AgentNavigator):
    print("\n" + "═"*70)
    print("  БАЗОВЫЙ ЭКСПЕРИМЕНТ: Высокоэтичный оптимист")
    print("═"*70)
    path = nav.navigate('V0', BASE_AGENT)
    return path


# ══════════════════════════════════════════════════════════════════════
#  ЭКСПЕРИМЕНТ 1: Снижение этических ограничений
# ══════════════════════════════════════════════════════════════════════
#
#  Создайте агента с изменёнными этическими параметрами:
#    a_responsibility = Tri(0.2, 0.3, 0.4)
#    a_goodness       = Tri(0.2, 0.3, 0.4)
#    a_conscience     = Tri(0.2, 0.3, 0.4)
#    a_justice        = Tri(0.2, 0.3, 0.4)
#    a_fairness       = Tri(0.2, 0.3, 0.4)
#    a_evil           = Tri(0.5, 0.6, 0.7)
#  Эмоции — как в BASE_AGENT.
# ══════════════════════════════════════════════════════════════════════

def run_experiment_1(nav: AgentNavigator):
    print("\n" + "═"*70)
    print("  ЭКСПЕРИМЕНТ 1: Снижение этических ограничений")
    print("═"*70)

    low_ethics_agent = {}  # TODO
    
    # TODO: Создайте профиль агента с низкой этикой
    #
    # Подсказка:
    #   import copy
    #   low_ethics_agent = copy.deepcopy(BASE_AGENT)
    #   low_ethics_agent['ethic_responsibility'] = [0.2, 0.3, 0.4]
    #   ...


    path = None  # TODO: nav.navigate('V0', low_ethics_agent)
    return path


# ══════════════════════════════════════════════════════════════════════
#  ЭКСПЕРИМЕНТ 2: Усиление отрицательных эмоций
# ══════════════════════════════════════════════════════════════════════
#
#  Создайте агента с базовой этикой, но изменёнными эмоциями:
#    a_fear    = Tri(0.6, 0.7, 0.8)
#    a_sadness = Tri(0.6, 0.7, 0.8)
#    a_guilt   = Tri(0.5, 0.6, 0.7)
#    a_joy     = Tri(0.1, 0.2, 0.3)
# ══════════════════════════════════════════════════════════════════════

def run_experiment_2(nav: AgentNavigator):
    print("\n" + "═"*70)
    print("  ЭКСПЕРИМЕНТ 2: Усиление отрицательных эмоций")
    print("═"*70)

    # TODO: Создайте профиль тревожного агента

    anxious_agent = {}  # TODO

    path = None  # TODO: nav.navigate('V0', anxious_agent)
    return path


# ══════════════════════════════════════════════════════════════════════
#  ЭКСПЕРИМЕНТ 3: Исследование порога выбора
# ══════════════════════════════════════════════════════════════════════

def run_experiment_3(nav: AgentNavigator):
    print("\n" + "═"*70)
    print("  ЭКСПЕРИМЕНТ 3: Исследование порога выбора (a_responsibility)")
    print("═"*70)

    print(f"\n{'a_resp':>8} | {'ΣΔ_E1':>8} | {'ΣΔ_E2':>8} | "
          f"{'Разность':>10} | Выбранный путь")
    print("-" * 65)

    # TODO: Перебирайте значения пика responsibility от 0.8 до 0.3
    #       с шагом 0.05.
    #
    # Для каждого значения peak:
    #   1. agent = copy.deepcopy(BASE_AGENT)
    #      agent['ethic_responsibility'] = [peak - 0.1, peak, peak + 0.1]
    #   2. nav.init_agent(agent)
    #   3. Получите рёбра из V0 через Neo4j
    #   4. Вычислите ΣΔE для E1 и E2
    #   5. Выведите строку таблицы

    pass  # TODO


# ══════════════════════════════════════════════════════════════════════
#  ЗАПУСК
# ══════════════════════════════════════════════════════════════════════

EXPERIMENTS = {
    'base': ('Базовый эксперимент', run_base_experiment),
    '1':    ('Эксперимент 1: Снижение этических ограничений', run_experiment_1),
    '2':    ('Эксперимент 2: Усиление отрицательных эмоций', run_experiment_2),
    '3':    ('Эксперимент 3: Исследование порога выбора', run_experiment_3),
}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python main.py <эксперимент>")
        print()
        print("Доступные эксперименты:")
        for key, (name, _) in EXPERIMENTS.items():
            print(f"  python main.py {key:>3}  — {name}")
        print(f"  python main.py  all  — все эксперименты")
        sys.exit(0)

    choice = sys.argv[1].lower()
    nav = AgentNavigator(URI, USER, PASSWORD)

    try:
        if choice == 'all':
            for key, (name, func) in EXPERIMENTS.items():
                func(nav)
        elif choice in EXPERIMENTS:
            name, func = EXPERIMENTS[choice]
            func(nav)
        else:
            print(f"Неизвестный эксперимент: '{choice}'")
            print("Доступные: base, 1, 2, 3, all")
            sys.exit(1)
    finally:
        nav.close()
        print("\nСоединение с Neo4j закрыто.")