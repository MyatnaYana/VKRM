import csv
import networkx as nx
import matplotlib.pyplot as plt


# Класс для описания агента (остается без изменений)
class Agent:
    def __init__(self, altruism=0.5, honesty=0.5, fairness=0.5, responsibility=0.5, malice=0.5):
        self.altruism = altruism
        self.honesty = honesty
        self.fairness = fairness
        self.responsibility = responsibility
        self.malice = malice

    def update_characteristics(self, action_weights):
        self.altruism += action_weights['altruism']
        self.honesty += action_weights['honesty']
        self.fairness += action_weights['fairness']
        self.responsibility += action_weights['responsibility']
        self.malice += action_weights['malice']

    def choose_action(self, available_actions):
        best_action = max(available_actions, key=lambda x: self.evaluate_action(x))
        self.explain_choice(best_action)
        return best_action

    def evaluate_action(self, action):
        weights = action['weights']
        score = (self.altruism * weights['altruism'] +
                 self.honesty * weights['honesty'] +
                 self.fairness * weights['fairness'] +
                 self.responsibility * weights['responsibility'] -
                 self.malice * weights['malice'])
        return score

    def explain_choice(self, chosen_action):
        weights = chosen_action['weights']
        print(f"Выбрано действие: {chosen_action['description']}")
        print(f"Altruism: {self.altruism} * {weights['altruism']} = {self.altruism * weights['altruism']}")
        print(f"Honesty: {self.honesty} * {weights['honesty']} = {self.honesty * weights['honesty']}")
        print(f"Fairness: {self.fairness} * {weights['fairness']} = {self.fairness * weights['fairness']}")
        print(
            f"Responsibility: {self.responsibility} * {weights['responsibility']} = {self.responsibility * weights['responsibility']}")
        print(f"Malice: {self.malice} * {weights['malice']} = {self.malice * weights['malice']}")
        print("-" * 50)

    def print_current_characteristics(self):
        print(f"Текущие характеристики агента: Altruism = {self.altruism}, Honesty = {self.honesty}, "
              f"Fairness = {self.fairness}, Responsibility = {self.responsibility}, Malice = {self.malice}")
        print("=" * 50)


# Класс для описания узла сценарной сети (остается без изменений)
class ScenarioNode:
    def __init__(self, description):
        self.description = description
        self.actions = []  # Список возможных действий с весами


# Функция для чтения сценарной сети из CSV файла
def load_scenario_network(filename):
    nodes = {}
    with open(filename, mode='r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            node_id = row['NodeID']
            if node_id not in nodes:
                nodes[node_id] = ScenarioNode(row['NodeDescription'])

            action = {
                'description': row['EdgeDescription'],
                'next_node': row['NextNodeID'],
                'weights': {
                    'altruism': float(row['Altruism']),
                    'honesty': float(row['Honesty']),
                    'fairness': float(row['Fairness']),
                    'responsibility': float(row['Responsibility']),
                    'malice': float(row['Malice'])
                }
            }
            nodes[node_id].actions.append(action)
    return nodes


# Функция для симуляции и сохранения пути агента
def simulate(agent, start_node, nodes):
    current_node = start_node
    path = []  # Список для сохранения пройденного пути
    while nodes[current_node].actions:
        print(f"Текущее состояние: {nodes[current_node].description}")
        available_actions = nodes[current_node].actions
        chosen_action = agent.choose_action(available_actions)
        print(f"Выбрано действие: {chosen_action['description']}")
        agent.update_characteristics(chosen_action['weights'])
        agent.print_current_characteristics()
        path.append((current_node, chosen_action['next_node']))  # Сохраняем путь
        current_node = chosen_action['next_node']

        if current_node == '0' or current_node not in nodes:
            print(
                f"Агент завершил сценарий в состоянии: {nodes[current_node].description if current_node in nodes else 'неизвестном состоянии'}")
            break
    return path  # Возвращаем путь


# Функция для построения визуализации графа
def visualize_graph(nodes, path):
    G = nx.DiGraph()

    # Добавляем узлы
    for node_id, node in nodes.items():
        G.add_node(node_id, label=node.description)

    # Добавляем рёбра (действия)
    for node_id, node in nodes.items():
        for action in node.actions:
            G.add_edge(node_id, action['next_node'], label=action['description'])

    # Определяем позиции для узлов
    pos = nx.spring_layout(G)

    # Рисуем все рёбра и узлы
    nx.draw(G, pos, with_labels=True, node_size=3000, node_color="lightblue", font_size=10, font_weight="bold")

    # Рисуем выделенный путь
    edge_colors = ['red' if (u, v) in path else 'black' for u, v in G.edges()]
    nx.draw_networkx_edges(G, pos, edge_color=edge_colors, width=2)

    # Отображаем подписи к рёбрам (действиям)
    edge_labels = nx.get_edge_attributes(G, 'label')
    nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels)

    plt.show()


# Загружаем сеть из файла
scenario_network_file = 'scenario.csv'  # путь к твоему файлу
nodes = load_scenario_network(scenario_network_file)

# Создаем агента и запускаем симуляцию
agent = Agent(altruism=0.1, honesty=0.7, fairness=0.5, responsibility=0.3, malice=0.8)
path = simulate(agent, '1', nodes)  # Симулируем и сохраняем путь

# Визуализируем граф
visualize_graph(nodes, path)

