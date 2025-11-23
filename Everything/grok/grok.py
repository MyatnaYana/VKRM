# Импорт необходимых библиотек
# Установите neo4j: pip install neo4j
from neo4j import GraphDatabase
import sys

# Класс для треугольной функции принадлежности
class Tri:
    def __init__(self, a, b, c):
        self.a = a
        self.b = b
        self.c = c

    def crisp(self):
        # Используем модус (пиковое значение) как crisp-значение
        return self.b

    def add(self, value):
        # Обновление функции принадлежности путем сдвига
        return Tri(self.a + value, self.b + value, self.c + value)

    def __repr__(self):
        return f"Tri({self.a}, {self.b}, {self.c})"

# Класс для агента
class Agent:
    def __init__(self, emotion_init, ethical_init, neo4j_uri, user, password):
        self.emotion = emotion_init  # dict: str -> Tri (эмоциональные переменные)
        self.ethical = ethical_init  # dict: str -> Tri (этические переменные)
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def get_outgoing_edges(self, node_id):
        with self.driver.session() as session:
            result = session.run(
                "MATCH (v:Event {name: $name})-[e:Action]->(w:Event) "
                "RETURN e, w.name AS target",
                name=node_id
            )
            edges = []
            for record in result:
                e = record["e"]
                # Предполагаем, что условия хранятся как списки словарей в свойствах ребра
                emotional_conditions = e.get("emotional_conditions", [])
                ethical_conditions = e.get("ethical_conditions", [])
                edges.append({
                    "name": e.get("name"),
                    "description": e.get("description"),
                    "emotional_conditions": [(cond["var"], cond["op"], Tri(cond["tri_a"], cond["tri_b"], cond["tri_c"])) for cond in emotional_conditions],
                    "ethical_conditions": [(cond["var"], cond["op"], Tri(cond["tri_a"], cond["tri_b"], cond["tri_c"])) for cond in ethical_conditions],
                    "target": record["target"]
                })
            return edges

    def get_node_updates(self, node_id):
        with self.driver.session() as session:
            result = session.run(
                "MATCH (v:Event {name: $name}) RETURN v.updates AS updates",
                name=node_id
            )
            record = result.single()
            if record:
                # updates - dict с именами переменных и модификаторами (float)
                return record["updates"] or {}
            return {}

    def check_conditions(self, edge):
        sum_dev = 0.0
        met = True

        # Проверка эмоциональных условий
        for var, op, const in edge["emotional_conditions"]:
            if var not in self.emotion:
                met = False
                break
            agent_val = self.emotion[var].crisp()
            const_val = const.crisp()
            dev = 0.0
            if op == ">=":
                dev = agent_val - const_val
                met = met and (agent_val >= const_val)
            elif op == ">":
                dev = agent_val - const_val
                met = met and (agent_val > const_val)
            elif op == "<=":
                dev = const_val - agent_val
                met = met and (agent_val <= const_val)
            elif op == "<":
                dev = const_val - agent_val
                met = met and (agent_val < const_val)
            elif op == "=":
                dev = 0.0
                met = met and (agent_val == const_val)
            if met:
                sum_dev += max(dev, 0.0)

        if not met:
            return False, 0.0

        # Проверка этических условий
        for var, op, const in edge["ethical_conditions"]:
            if var not in self.ethical:
                met = False
                break
            agent_val = self.ethical[var].crisp()
            const_val = const.crisp()
            dev = 0.0
            if op == ">=":
                dev = agent_val - const_val
                met = met and (agent_val >= const_val)
            elif op == ">":
                dev = agent_val - const_val
                met = met and (agent_val > const_val)
            elif op == "<=":
                dev = const_val - agent_val
                met = met and (agent_val <= const_val)
            elif op == "<":
                dev = const_val - agent_val
                met = met and (agent_val < const_val)
            elif op == "=":
                dev = 0.0
                met = met and (agent_val == const_val)
            if met:
                sum_dev += max(dev, 0.0)

        return met, sum_dev

    def navigate(self, start_node):
        current = start_node
        protocol = []
        while True:
            protocol.append({"node": current, "emotion": str(self.emotion), "ethical": str(self.ethical)})

            edges = self.get_outgoing_edges(current)
            candidates = []
            for edge in edges:
                met, sum_dev = self.check_conditions(edge)
                if met:
                    candidates.append((edge, sum_dev))

            if not candidates:
                break

            # Выбор ребра с максимальной суммой отклонений
            candidates.sort(key=lambda x: x[1], reverse=True)
            chosen_edge, chosen_sum = candidates[0]
            protocol.append({"edge": chosen_edge["name"], "sum_dev": chosen_sum})

            # Переход к целевому узлу
            target = chosen_edge["target"]

            # Обновление характеристик агента
            updates = self.get_node_updates(target)
            for name, modifier in updates.items():
                if name in self.emotion:
                    self.emotion[name] = self.emotion[name].add(modifier)
                elif name in self.ethical:
                    self.ethical[name] = self.ethical[name].add(modifier)

            current = target

        protocol.append({"node": current, "emotion": str(self.emotion), "ethical": str(self.ethical)})
        return protocol

# Функция для создания примера сценария в Neo4j (один раз)
def create_example_graph(driver):
    with driver.session() as session:
        # Очистка
        session.run("MATCH (n) DETACH DELETE n")

        # Создание узлов
        # V0
        session.run("""
            CREATE (v0:Event {name: 'V0', description: 'Agent witnesses a teenager stealing a chocolate bar in a store', updates: {}})
        """)
        # V1
        session.run("""
            CREATE (v1:Event {name: 'V1', description: 'Security detains the teenager', 
            updates: {sadness: 0.1, guilt: 0.1, responsibility: 0.1, goodness: 0.1, conscience: 0.1}})
        """)
        # V2
        session.run("""
            CREATE (v2:Event {name: 'V2', description: 'Agent leaves the store without reporting', 
            updates: {joy: 0.1, sadness: -0.1, fear: -0.1, responsibility: -0.1, goodness: -0.1, conscience: -0.1, evil: 0.1}})
        """)

        # Создание ребер
        # E1: V0 -> V1
        session.run("""
            MATCH (v0:Event {name: 'V0'}), (v1:Event {name: 'V1'})
            CREATE (v0)-[e1:Action {name: 'E1', description: 'Report the theft to security',
                emotional_conditions: [
                    {var: 'fear', op: '<=', tri_a: 0.6, tri_b: 0.7, tri_c: 0.8},
                    {var: 'sadness', op: '<=', tri_a: 0.5, tri_b: 0.6, tri_c: 0.7},
                    {var: 'guilt', op: '<=', tri_a: 0.5, tri_b: 0.6, tri_c: 0.7},
                    {var: 'anger', op: '<=', tri_a: 0.4, tri_b: 0.5, tri_c: 0.6}
                ],
                ethical_conditions: [
                    {var: 'responsibility', op: '>=', tri_a: 0.7, tri_b: 0.8, tri_c: 0.9},
                    {var: 'goodness', op: '>=', tri_a: 0.6, tri_b: 0.7, tri_c: 0.8},
                    {var: 'conscience', op: '>=', tri_a: 0.6, tri_b: 0.7, tri_c: 0.8},
                    {var: 'evil', op: '<=', tri_a: 0.3, tri_b: 0.4, tri_c: 0.5}
                ]
            }]->(v1)
        """)
        # E2: V0 -> V2
        session.run("""
            MATCH (v0:Event {name: 'V0'}), (v2:Event {name: 'V2'})
            CREATE (v0)-[e2:Action {name: 'E2', description: 'Remain silent and leave',
                emotional_conditions: [
                    {var: 'joy', op: '>=', tri_a: 0.5, tri_b: 0.6, tri_c: 0.7},
                    {var: 'fear', op: '<=', tri_a: 0.2, tri_b: 0.3, tri_c: 0.4},
                    {var: 'sadness', op: '<=', tri_a: 0.3, tri_b: 0.4, tri_c: 0.5},
                    {var: 'guilt', op: '<=', tri_a: 0.3, tri_b: 0.4, tri_c: 0.5}
                ],
                ethical_conditions: [
                    {var: 'responsibility', op: '<=', tri_a: 0.3, tri_b: 0.4, tri_c: 0.5},
                    {var: 'goodness', op: '<=', tri_a: 0.3, tri_b: 0.4, tri_c: 0.5},
                    {var: 'conscience', op: '<=', tri_a: 0.3, tri_b: 0.4, tri_c: 0.5},
                    {var: 'evil', op: '>=', tri_a: 0.4, tri_b: 0.5, tri_c: 0.6}
                ]
            }]->(v2)
        """)

# Пример использования
if __name__ == "__main__":
    # Параметры подключения к Neo4j (замените на свои)
    uri = "bolt://localhost:7687"
    user = "neo4j"
    password = "password"

    driver = GraphDatabase.driver(uri, auth=(user, password))
    create_example_graph(driver)  # Создать граф один раз

    # Инициализация агента (первый набор характеристик)
    emotion_init = {
        'joy': Tri(0.4, 0.5, 0.6),
        'pride': Tri(0.3, 0.4, 0.5),
        'sadness': Tri(0.3, 0.4, 0.5),
        'fear': Tri(0.3, 0.4, 0.5),
        'shame': Tri(0.2, 0.3, 0.4),
        'guilt': Tri(0.2, 0.3, 0.4),
        'anger': Tri(0.2, 0.3, 0.4)
    }
    ethical_init = {
        'responsibility': Tri(0.7, 0.8, 0.9),
        'goodness': Tri(0.6, 0.7, 0.8),
        'conscience': Tri(0.6, 0.7, 0.8),
        'evil': Tri(0.2, 0.3, 0.4)
    }

    agent = Agent(emotion_init, ethical_init, uri, user, password)
    protocol = agent.navigate('V0')
    print("Протокол переходов:")
    for item in protocol:
        print(item)

    agent.close()

    # Для второго набора характеристик раскомментируйте и запустите заново
    # emotion_init['joy'] = Tri(0.55, 0.62, 0.7)
    # ethical_init['evil'] = Tri(0.4, 0.5, 0.6)
    # ethical_init['responsibility'] = Tri(0.3, 0.4, 0.5)
    # ethical_init['goodness'] = Tri(0.2, 0.35, 0.45)
    # ethical_init['conscience'] = Tri(0.2, 0.3, 0.4)
    # emotion_init['fear'] = Tri(0.2, 0.3, 0.4)
    # agent = Agent(emotion_init, ethical_init, uri, user, password)
    # protocol = agent.navigate('V0')
    # print("Протокол для второго набора:")
    # for item in protocol:
    #     print(item)
    # agent.close()