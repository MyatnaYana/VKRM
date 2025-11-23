class Agent:
    def __init__(self, start_node, emotions, ethics):
        self.current_node = start_node
        self.emotions = emotions
        self.ethics = ethics

    def update_characteristics(self, updates):
        """
        Обновляем характеристики агента на основе словаря updates.
        updates = {'sadness': 0.1, 'guilt': 0.1, ...}
        Метод корректно обновляет все три компонента Tri: [min, mean, max].
        """
        for k, v in updates.items():
            if k in self.emotions and isinstance(self.emotions[k], list):
                self.emotions[k] = [round(x + v, 3) for x in self.emotions[k]]
            elif k in self.ethics and isinstance(self.ethics[k], list):
                self.ethics[k] = [round(x + v, 3) for x in self.ethics[k]]

    def check_conditions(self, edge_props):
        """
        Проверяем, удовлетворяет ли агент условиям ребра cond_*
        Простая логика:
        - cond_em_*: текущая характеристика <= max значения Tri из условия
        - cond_eth_*: текущая характеристика >= min значения Tri из условия
        """
        for k, v in edge_props.items():
            if not k.startswith("cond_"):
                continue

            attr = k.replace("cond_em_", "").replace("cond_eth_", "")
            if k.startswith("cond_em_") and attr in self.emotions:
                if self.emotions[attr][1] > v[2]:  # проверка средней Tri <= max условия
                    return False
            elif k.startswith("cond_eth_") and attr in self.ethics:
                if self.ethics[attr][1] < v[0]:  # проверка средней Tri >= min условия
                    return False
        return True

    def move(self, connector):
        edges = connector.get_outgoing_edges(self.current_node)
        if not edges:
            print("No outgoing edges, agent stops.")
            return False

        print(f"--- Evaluating outgoing edges from {self.current_node} ---")
        valid_edges = []

        for edge in edges:
            print(f"Edge {edge['type']}: {edge['description']}")
            print("  Conditions:")
            for k, v in edge['props'].items():
                if k.startswith("cond_"):
                    print(f"    {k} = {v}")
            # Проверяем условия для данного ребра
            if self.check_conditions(edge['props']):
                print("  Edge is valid based on current agent characteristics.")
                valid_edges.append(edge)
            else:
                print("  Edge NOT valid based on current agent characteristics.")

        if not valid_edges:
            print("No valid edges to move, agent stops.")
            return False

        # Выбираем ребро (например, первое валидное)
        selected_edge = valid_edges[0]

        print(f"Agent moves from {self.current_node} to {selected_edge['target']} via {selected_edge['type']}")

        # Применяем обновления характеристик
        updates = {k.replace("update_", ""): v for k,v in selected_edge['props'].items() if k.startswith("update_")}
        if updates:
            print("  Applying updates:")
            for k, v in updates.items():
                print(f"    {k} += {v}")
        self.update_characteristics(updates)

        self.current_node = selected_edge['target']
        return True


    def print_status(self):
        print(f"--- Current Node: {self.current_node} ---")
        print("Emotions:")
        for k,v in self.emotions.items():
            print(f"  {k}: {v}")
        print("Ethics:")
        for k,v in self.ethics.items():
            print(f"  {k}: {v}")
