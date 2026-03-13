import csv
import networkx as nx
import matplotlib.pyplot as plt


# Класс для описания агента
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
        return best_action

    def evaluate_action(self, action):
        weights = action['weights']
        score = (self.altruism * weights['altruism'] +
                 self.honesty * weights['honesty'] +
                 self.fairness * weights['fairness'] +
                 self.responsibility * weights['responsibility'] -
                 self.malice * weights['malice'])
        return score

    def print_current_characteristics(self):
        print(f"Текущие характеристики агента: Altruism = {self.altruism}, Honesty = {self.honesty}, "
              f"Fairness = {self.fairness}, Responsibility = {self.responsibility}, Malice = {self.malice}")
        print("=" * 50)


# Класс для описания узла сценарной сети
class ScenarioNode:
    def __init__(self, description, node_weights=None):
        self.description = description
        self.actions = []  # Список возможных действий с весами
        self.node_weights = node_weights if node_weights else {
            'altruism': 0,
            'honesty': 0,
            'fairness': 0,
            'responsibility': 0,
            'malice': 0
        }

    def apply_node_weights(self, agent):
        print(f"Характеристики узла: {self.node_weights}")
        agent.update_characteristics(self.node_weights)


# Функция для чтения сценарной сети из CSV файла
def load_scenario_network(filename):
    nodes = {}
    with open(filename, mode='r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            node_id = row['NodeID']
            if node_id not in nodes:
                node_weights = {
                    'altruism': float(row.get('NodeAltruism', 0)),
                    'honesty': float(row.get('NodeHonesty', 0)),
                    'fairness': float(row.get('NodeFairness', 0)),
                    'responsibility': float(row.get('NodeResponsibility', 0)),
                    'malice': float(row.get('NodeMalice', 0))
                }
                nodes[node_id] = ScenarioNode(row['NodeDescription'], node_weights)

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
        # Вывод текущего состояния
        print(f"Текущее состояние: Узел {current_node}, Описание узла: {nodes[current_node].description}")
        agent.print_current_characteristics()

        # Применяем веса узла
        print("\nПрименение характеристик узла:")
        nodes[current_node].apply_node_weights(agent)
        agent.print_current_characteristics()

        # Выбор действия
        available_actions = nodes[current_node].actions
        chosen_action = agent.choose_action(available_actions)
        print(f"\nВыбрано действие: {chosen_action['description']}")
        print(f"Переход на узел: {chosen_action['next_node']}")

        # Применяем веса действия
        print("\nПрименение характеристик действия:")
        agent.update_characteristics(chosen_action['weights'])
        agent.print_current_characteristics()

        # Сохраняем путь
        path.append((current_node, chosen_action['next_node']))
        current_node = chosen_action['next_node']

        # Проверка на завершение сценария
        if current_node == '0' or current_node not in nodes:
            print(f"\nАгент завершил сценарий в состоянии: Узел {current_node}")
            break
        print("\n" + "=" * 50 + "\n")
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