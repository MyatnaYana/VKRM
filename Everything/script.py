from graphviz import Digraph

# Создаем граф с помощью Graphviz
dot = Digraph(comment="Сценарная сеть")

# Добавляем узлы
dot.node("start", "Просыпаешься, ожидаешь звонка")
dot.node("cafe", "Находишь бумажник в кафе")
dot.node("leave_wallet", "Оставить бумажник")
dot.node("return_wallet", "Передать кассиру")
dot.node("work", "Приходишь на работу")
dot.node("help_dmitry", "Помочь Дмитрию")
dot.node("decline_dmitry", "Отказать Дмитрию")
dot.node("boss_call", "Начальство вызывает")
dot.node("explain_boss", "Объяснить ситуацию")
dot.node("accept_criticism", "Молча принять критику")
dot.node("no_bonus", "Лишение премии")
dot.node("keep_working", "Продолжать работать")
dot.node("doubt_yourself", "Начать сомневаться в себе")
dot.node("colleague_criticized", "Коллега несправедливо критикует другого")
dot.node("defend_colleague", "Вмешаться")
dot.node("ignore_colleague", "Пройти мимо")
dot.node("colleagues_attack", "Коллеги начинают критиковать тебя")
dot.node("argue_back", "Доказывать свою правоту")
dot.node("smooth_conflict", "Сгладить ситуацию")
dot.node("walk_away", "Уйти от конфликта")

# Добавляем связи (рёбра)
edges = [
    ("start", "cafe"),
    ("cafe", "leave_wallet"),
    ("cafe", "return_wallet"),
    ("leave_wallet", "work"),
    ("return_wallet", "work"),
    ("work", "help_dmitry"),
    ("work", "decline_dmitry"),
    ("help_dmitry", "boss_call"),
    ("boss_call", "explain_boss"),
    ("boss_call", "accept_criticism"),
    ("explain_boss", "no_bonus"),
    ("accept_criticism", "no_bonus"),
    ("no_bonus", "keep_working"),
    ("no_bonus", "doubt_yourself"),
    ("work", "colleague_criticized"),
    ("colleague_criticized", "defend_colleague"),
    ("colleague_criticized", "ignore_colleague"),
    ("defend_colleague", "colleagues_attack"),
    ("colleagues_attack", "argue_back"),
    ("colleagues_attack", "smooth_conflict"),
    ("colleagues_attack", "walk_away")
]

for edge in edges:
    dot.edge(edge[0], edge[1])

# Сохраняем и отображаем
# Если нужно сохранить в другом месте, то нужно изменить путь
graph_path = "scenario_network"
dot.render(graph_path, format="png")

# Показываем изображение
graph_path += ".png"
graph_path
