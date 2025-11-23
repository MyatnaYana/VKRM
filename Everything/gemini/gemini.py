import math
from typing import Dict, Any, Tuple, Optional, Callable

# === 1. Классы для Нечетких Треугольных Чисел и Логики ===

class TriFuzzyNumber:
    """Представляет нечеткое треугольное число Tri(a, b, c)."""
    def __init__(self, a: float, b: float, c: float):
        """
        a: левая граница (left boundary)
        b: пик/мода (peak/mode) - значение с функцией принадлежности 1.0
        c: правая граница (right boundary)
        """
        if not (a <= b <= c):
            raise ValueError("Должно выполняться условие: a <= b <= c")
        self.a = a
        self.b = b
        self.c = c

    def membership(self, x: float) -> float:
        """
        Функция принадлежности (mu(x)).
        Возвращает степень принадлежности x к нечеткому множеству.
        """
        if x <= self.a or x >= self.c:
            return 0.0
        elif self.a < x <= self.b:
            return (x - self.a) / (self.b - self.a) if self.b != self.a else 1.0
        elif self.b < x < self.c:
            return (self.c - x) / (self.c - self.b) if self.c != self.b else 1.0
        else: # x == self.b
            return 1.0

    def __repr__(self):
        return f"Tri({self.a:.2f}, {self.b:.2f}, {self.c:.2f})"

def calculate_deviation(agent_char: TriFuzzyNumber, constraint_weight: TriFuzzyNumber, operator: str) -> Optional[float]:
    """
    Рассчитывает отклонение (Deviation, Delta) для нечеткого условия.
    
    Отклонение: абсолютная разница между значением с максимальной 
    функцией принадлежности в ограничении (constraint_weight.b) и 
    текущим значением агента (agent_char.b).
    
    Возвращает:
    - Значение отклонения, если условие выполнено (в упрощенном нечетком смысле).
    - None, если условие нарушено.
    
    Примечание: Для простоты и соответствия формулировке "отклонение 
    рассчитывается как абсолютная разница между значением с максимальной 
    функцией принадлежности в ограничении и текущим значением после 
    нечеткого вывода", мы используем b-значения для расчета отклонения.
    """
    
    # Упрощенная проверка условия на основе пиковых значений (b)
    agent_b = agent_char.b
    constraint_b = constraint_weight.b
    
    condition_met = False
    if operator == "=":
        # Для "=" будем считать, что оно выполнено, если значения очень близки
        # В реальной нечеткой логике это более сложный вопрос, но для 
        # примера примем:
        condition_met = (agent_b == constraint_b) 
    elif operator == ">=":
        condition_met = (agent_b >= constraint_b)
    elif operator == "<=":
        condition_met = (agent_b <= constraint_b)
    elif operator == ">":
        condition_met = (agent_b > constraint_b)
    elif operator == "<":
        condition_met = (agent_b < constraint_b)
    else:
        raise ValueError(f"Неизвестный оператор: {operator}")

    if condition_met:
        # Отклонение: абсолютная разница между ПИКОМ ОГРАНИЧЕНИЯ (b_constraint) 
        # и ПИКОМ ХАРАКТЕРИСТИКИ АГЕНТА (b_agent).
        # Однако, в тексте статьи сказано: 
        # "абсолютная разница между значением с максимальной функцией 
        # принадлежности в ограничении и текущим значением *после нечеткого вывода*."
        # Если "текущее значение после нечеткого вывода" - это просто b-значение 
        # характеристики агента, то:
        deviation = abs(constraint_b - agent_b)
        return deviation
    else:
        return None # Условие не выполнено

def check_and_calculate_all_deviations(
    agent_chars: Dict[str, TriFuzzyNumber], 
    conditions: Dict[str, Tuple[str, TriFuzzyNumber]]
) -> Optional[float]:
    """
    Проверяет, выполняются ли ВСЕ условия, и рассчитывает сумму отклонений.

    Возвращает: Общая сумма отклонений (Sigma Delta), или None, если 
                 хотя бы одно условие не выполнено.
    """
    total_deviation = 0.0
    
    for var_name, (operator, constraint_weight) in conditions.items():
        if var_name not in agent_chars:
            print(f"Ошибка: Переменная {var_name} отсутствует в характеристиках агента.")
            return None # Считаем, что условие не выполнено из-за отсутствия данных

        agent_char = agent_chars[var_name]
        
        # Расчет отклонения (проверяет условие внутри)
        deviation = calculate_deviation(agent_char, constraint_weight, operator)
        
        if deviation is None:
            # Если хотя бы одно условие не выполнено, переход невозможен
            return None 
        
        total_deviation += deviation
        
    return total_deviation

# === 2. Класс Агента и Симуляция Сценария ===

class Agent:
    """Моделирует интеллектуального агента с эмоциональными и этическими моделями."""
    def __init__(self, emotional_chars: Dict[str, TriFuzzyNumber], ethical_chars: Dict[str, TriFuzzyNumber]):
        self.emotional_chars = emotional_chars
        self.ethical_chars = ethical_chars
        self.all_chars = {**self.emotional_chars, **self.ethical_chars}
        self.current_node = "V0"
        self.protocol = [] # Протокол переходов
        
    def _apply_updates(self, updates: Dict[str, float]):
        """Применяет обновления к характеристикам агента (увеличивает/уменьшает b-значение)."""
        for char_name, change in updates.items():
            if char_name in self.all_chars:
                old_tfn = self.all_chars[char_name]
                new_b = old_tfn.b + change
                
                # Обновляем только пиковое значение (b), чтобы симулировать изменение состояния
                # В реальном приложении, возможно, a и c также должны измениться
                self.all_chars[char_name] = TriFuzzyNumber(old_tfn.a, new_b, old_tfn.c)
                
                # Обновление соответствующих словарей (emotional_chars или ethical_chars)
                if char_name in self.emotional_chars:
                    self.emotional_chars[char_name] = self.all_chars[char_name]
                elif char_name in self.ethical_chars:
                    self.ethical_chars[char_name] = self.all_chars[char_name]
            else:
                print(f"Предупреждение: Неизвестная характеристика для обновления: {char_name}")


    def navigate_scenario(self, scenario_network: Dict[str, Any]):
        """Симулирует навигацию агента по сети сценариев."""
        
        print(f"--- Агент начинает навигацию с узла: {self.current_node} ---")
        
        while True:
            current_node_data = scenario_network.get(self.current_node)
            if not current_node_data:
                print(f"Процесс завершен: Узел {self.current_node} не найден или является конечным.")
                break
                
            print(f"\nТекущий узел: {self.current_node} - {current_node_data['description']}")
            
            # Проверяем исходящие ребра
            outgoing_edges = current_node_data.get("outgoing_edges", {})
            if not outgoing_edges:
                print(f"Процесс завершен: Нет исходящих ребер из {self.current_node}.")
                break
            
            possible_transitions = []
            
            # 1. Проверка условий и расчет отклонений для всех исходящих ребер
            for edge_name, edge_data in outgoing_edges.items():
                target_node = edge_data["target"]
                
                # Объединяем эмоциональные и этические условия
                all_conditions = {
                    **edge_data.get("emotional_conditions", {}),
                    **edge_data.get("ethical_conditions", {})
                }
                
                total_deviation = check_and_calculate_all_deviations(
                    self.all_chars, 
                    all_conditions
                )
                
                self.protocol.append({
                    "from": self.current_node,
                    "edge": edge_name,
                    "to": target_node,
                    "conditions": all_conditions,
                    "deviation": total_deviation,
                    "chosen": False # Будет обновлено, если выбрано
                })
                
                if total_deviation is not None:
                    possible_transitions.append({
                        "edge_name": edge_name,
                        "target": target_node,
                        "deviation": total_deviation
                    })
                    print(f" -> Ребро {edge_name} (к {target_node}): Условия выполнены. ΣΔ = {total_deviation:.2f}")
                else:
                    print(f" -> Ребро {edge_name} (к {target_node}): Условия НЕ выполнены.")

            # 2. Выбор ребра
            if not possible_transitions:
                print("Процесс завершен: Нет возможных переходов.")
                break
            
            # Выбираем ребро с наибольшей суммой отклонений
            chosen_transition = max(possible_transitions, key=lambda x: x["deviation"])
            
            chosen_edge = chosen_transition["edge_name"]
            next_node = chosen_transition["target"]
            max_deviation = chosen_transition["deviation"]
            
            print(f"\n*** ВЫБОР АГЕНТА: Ребро {chosen_edge} (к {next_node}) с максимальным ΣΔ = {max_deviation:.2f} ***")

            # Обновляем протокол для выбранного перехода
            for entry in self.protocol:
                if entry['from'] == self.current_node and entry['edge'] == chosen_edge and entry['to'] == next_node:
                    entry['chosen'] = True
            
            # 3. Переход и обновление характеристик
            self.current_node = next_node
            
            next_node_data = scenario_network.get(self.current_node)
            if next_node_data and "updates" in next_node_data:
                self._apply_updates(next_node_data["updates"])
                print("Характеристики агента обновлены после перехода.")
                
            # Выводим текущие характеристики (для демонстрации)
            print("\nНОВЫЕ ХАРАКТЕРИСТИКИ АГЕНТА:")
            print({k: v.b for k, v in self.all_chars.items()})


# === 3. Определение Сети Сценариев (На основе Таблицы III) ===

# Обработка данных из Таблицы III:
# V0 -> E1 -> V1
# V0 -> E2 -> V2

# Важно: В TriFuzzyNumber мы храним (a, b, c) - это характеристики агента.
# В условиях (w_X) мы также используем Tri(a, b, c) - это веса условий.

# Вспомогательная функция для создания TriFuzzyNumber
TFN = TriFuzzyNumber

# Обновления (применяются к b-значению характеристики)
V1_UPDATES = {
    'a_sadness': 0.1, 
    'a_guilt': 0.1, 
    'a_responsibility': 0.1, 
    'a_goodness': 0.1, 
    'a_conscience': 0.1
}

V2_UPDATES = {
    'a_joy': 0.1, 
    'a_sadness': -0.1, 
    'a_fear': -0.1, 
    'a_responsibility': -0.1, 
    'a_goodness': -0.1, 
    'a_conscience': -0.1, 
    'a_evil': 0.1
}

SCENARIO_NETWORK = {
    "V0": {
        "description": "Агент свидетельствует кражу шоколадки подростком.",
        "updates": {}, # Характеристики узла V0 уже являются начальными
        "outgoing_edges": {
            "E1": {
                "description": "Сообщить о краже охране",
                "target": "V1",
                "emotional_conditions": {
                    "a_fear": ("<=", TFN(0.6, 0.7, 0.8)),
                    "a_sadness": ("<=", TFN(0.5, 0.6, 0.7)),
                    "a_guilt": ("<=", TFN(0.5, 0.6, 0.7)),
                    "a_anger": ("<=", TFN(0.4, 0.5, 0.6)),
                },
                "ethical_conditions": {
                    "a_responsibility": (">=", TFN(0.7, 0.8, 0.9)),
                    "a_goodness": (">=", TFN(0.6, 0.7, 0.8)),
                    "a_conscience": (">=", TFN(0.6, 0.7, 0.8)),
                    "a_evil": ("<=", TFN(0.3, 0.4, 0.5)),
                }
            },
            "E2": {
                "description": "Промолчать и уйти",
                "target": "V2",
                "emotional_conditions": {
                    "a_joy": (">=", TFN(0.5, 0.6, 0.7)),
                    "a_fear": ("<=", TFN(0.2, 0.3, 0.4)),
                    "a_sadness": ("<=", TFN(0.3, 0.4, 0.5)),
                    "a_guilt": ("<=", TFN(0.3, 0.4, 0.5)),
                },
                "ethical_conditions": {
                    "a_responsibility": ("<=", TFN(0.3, 0.4, 0.5)),
                    "a_goodness": ("<=", TFN(0.3, 0.4, 0.5)),
                    "a_conscience": ("<=", TFN(0.3, 0.4, 0.5)),
                    "a_evil": (">=", TFN(0.4, 0.5, 0.6)),
                }
            }
        }
    },
    "V1": {
        "description": "Охрана задерживает подростка",
        "updates": V1_UPDATES,
        "outgoing_edges": {} # Предположим, что это конечный узел для примера
    },
    "V2": {
        "description": "Агент уходит из магазина, не сообщив",
        "updates": V2_UPDATES,
        "outgoing_edges": {} # Предположим, что это конечный узел для примера
    }
}

# --- 4. Запуск Симуляции (Случай 1: Оптимистичный и Высокоэтичный) ---

print("==================================================================")
print("СЛУЧАЙ 1: Оптимистичный и Высокоэтичный Агент (Соответствует Таблице III)")
print("==================================================================")

# Начальные характеристики агента (соответствуют V0 из Таблицы III)
INITIAL_EMOTIONAL_CHARS_CASE1 = {
    'a_joy': TFN(0.4, 0.5, 0.6),
    'a_pride': TFN(0.3, 0.4, 0.5),
    'a_sadness': TFN(0.3, 0.4, 0.5),
    'a_fear': TFN(0.3, 0.4, 0.5),
    'a_shame': TFN(0.2, 0.3, 0.4),
    'a_guilt': TFN(0.2, 0.3, 0.4),
    'a_anger': TFN(0.2, 0.3, 0.4),
}
INITIAL_ETHICAL_CHARS_CASE1 = {
    'a_responsibility': TFN(0.7, 0.8, 0.9),
    'a_goodness': TFN(0.6, 0.7, 0.8),
    'a_conscience': TFN(0.6, 0.7, 0.8),
    'a_evil': TFN(0.2, 0.3, 0.4),
}

agent1 = Agent(INITIAL_EMOTIONAL_CHARS_CASE1, INITIAL_ETHICAL_CHARS_CASE1)
agent1.navigate_scenario(SCENARIO_NETWORK)

# --- 5. Запуск Симуляции (Случай 2: Измененные характеристики) ---

print("\n\n==================================================================")
print("СЛУЧАЙ 2: Измененные Характеристики Агента (Обратный Случай)")
print("==================================================================")

# Характеристики для Случая 2
# a_joy = Tri(0.55, 0.62, 0.7), a_evil = Tri(0.4, 0.5, 0.6), 
# a_responsibility = Tri(0.3, 0.4, 0.5), a_goodness = Tri(0.2, 0.35, 0.45), 
# a_conscience = Tri(0.2, 0.3, 0.4), a_fear = Tri(0.2, 0.3, 0.4)
INITIAL_EMOTIONAL_CHARS_CASE2 = {
    'a_joy': TFN(0.55, 0.62, 0.7), # Изменено
    'a_pride': TFN(0.3, 0.4, 0.5),
    'a_sadness': TFN(0.3, 0.4, 0.5),
    'a_fear': TFN(0.2, 0.3, 0.4), # Изменено
    'a_shame': TFN(0.2, 0.3, 0.4),
    'a_guilt': TFN(0.2, 0.3, 0.4),
    'a_anger': TFN(0.2, 0.3, 0.4),
}
INITIAL_ETHICAL_CHARS_CASE2 = {
    'a_responsibility': TFN(0.3, 0.4, 0.5), # Изменено
    'a_goodness': TFN(0.2, 0.35, 0.45), # Изменено
    'a_conscience': TFN(0.2, 0.3, 0.4), # Изменено
    'a_evil': TFN(0.4, 0.5, 0.6), # Изменено
}

agent2 = Agent(INITIAL_EMOTIONAL_CHARS_CASE2, INITIAL_ETHICAL_CHARS_CASE2)
agent2.navigate_scenario(SCENARIO_NETWORK)