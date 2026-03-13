#Простой пример графа
from graphviz import Digraph

# Создаём направленный граф
dot = Digraph()

# Добавляем вершины
dot.node('A', 'Node A')
dot.node('B', 'Node B')
dot.node('C', 'Node C')

# Добавляем рёбра
dot.edge('A', 'B')
dot.edge('B', 'C')
dot.edge('C', 'A')

# Сохраняем граф
dot.render('graph2', format='png', cleanup=True)

print("Граф сохранён как graph2.png")

