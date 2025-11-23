from db import Neo4jConnector
from agent import Agent

# Настройки соединения
URI = "neo4j://127.0.0.1:7687"
USER = "neo4j"
PASSWORD = "neo4jjjj"

connector = Neo4jConnector(URI, USER, PASSWORD)

# Загружаем начальные характеристики агента из V0
emotions, ethics = connector.get_node_characteristics("V0")
agent = Agent("V0", emotions, ethics)

agent.print_status()  # печатаем статус перед первым движением

while True:
    moved = agent.move(connector)
    if moved:
        agent.print_status()
    else:
        break

print("Agent finished moving through the scenario network.")
connector.close()
