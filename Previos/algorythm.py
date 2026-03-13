import pandas as pd

class Agent:
    def __init__(self, optimism, pessimism, aggressiveness, fearfulness, indifference):
        self.traits = {
            'Joy': optimism,
            'Sadness': pessimism,
            'Anger': aggressiveness,
            'Fear': fearfulness,
            'Calm': indifference
        }

    def choose_next_node(self, current_node, df):
        """Выбирает следующий узел на основе характеристик агента и весов узлов."""
        available_transitions = df[df['NodeID'] == current_node]
        
        if available_transitions.empty:
            return None  # Конец пути
        
        best_node = None
        best_score = float('-inf')
        
        for _, row in available_transitions.iterrows():
            score = sum(self.traits[emotion] * row[emotion] for emotion in self.traits)
            if score > best_score:
                best_score = score
                best_node = row['NextNodeID']
        
        return best_node

# Загружаем CSV-файл
df = pd.read_csv("scenario_network.csv")

# Создаем агента (пример: Оптимистичный, но слегка пугливый)
agent = Agent(optimism=0.7, pessimism=0.1, aggressiveness=0.1, fearfulness=0.3, indifference=0.2)

# Запускаем агента из узла 1
current_node = 1
while current_node != 0:
    print(f"Агент находится в узле {current_node}: {df[df['NodeID'] == current_node]['NodeDescription'].values[0]}")
    current_node = agent.choose_next_node(current_node, df)
print(f"Сценарий завершен.")
