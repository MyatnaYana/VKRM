from neo4j import GraphDatabase
import sys

class AgentNavigator:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.agent = {}          # текущие пиковые значения (b из Tri)
        self.path = []           # список (state_id, edge_id, next_id, sum_delta)
        self.protocol = []       # протокол всех альтернатив на каждом шаге

    def close(self):
        self.driver.close()

    def _get_peak(self, tri_list):
        """Возвращает пик треугольной функции (среднее значение)"""
        if isinstance(tri_list, list) and len(tri_list) == 3:
            return float(tri_list[1])
        return 0.0

    def init_agent_from_node(self, start_id: str):
        """Инициализируем агента пиками из стартового узла"""
        with self.driver.session() as session:
            result = session.run(
                "MATCH (s:State {id: $id}) RETURN s",
                id=start_id
            )
            record = result.single()
            if not record:
                raise ValueError(f"Узел {start_id} не найден")
            node = record['s']
            self.agent.clear()
            for key, value in node.items():
                if (key.startswith('emotion_') or key.startswith('ethic_')):
                    self.agent[key] = self._get_peak(value)
        print(f"Агент инициализирован из {start_id}. Текущие значения: {self.agent}")

    def set_custom_agent(self, custom_peaks: dict):
        """Для экспериментов — задать свои пиковые значения (например, низкоэтичный агент)"""
        self.agent = custom_peaks.copy()
        print(f"Агент инициализирован кастомными значениями: {self.agent}")

    def _compute_deviation(self, edge_props: dict) -> float:
        """Вычисляем ΣΔE — сумму абсолютных отклонений по всем условиям"""
        total = 0.0
        for key, value in edge_props.items():
            if key.startswith('cond_') and (key.endswith('_le') or key.endswith('_ge')):
                # извлекаем имя свойства агента
                if key.startswith('cond_em_'):
                    prop = 'emotion_' + key[8:-3]
                elif key.startswith('cond_eth_'):
                    prop = 'ethic_' + key[9:-3]
                else:
                    continue
                agent_val = self.agent.get(prop, 0.0)
                cond_peak = self._get_peak(value)
                total += abs(cond_peak - agent_val)
        return round(total, 3)

    def _apply_updates(self, edge_props: dict):
        """Применяем обновления к агенту"""
        for key, delta in edge_props.items():
            if key.startswith('update_'):
                if key.startswith('update_em_'):
                    prop = 'emotion_' + key[10:]
                elif key.startswith('update_eth_'):
                    prop = 'ethic_' + key[10:]
                else:
                    prop = key[7:]  # fallback
                self.agent[prop] = self.agent.get(prop, 0.0) + float(delta)

    def navigate(self, start_id: str = 'V0'):
        """Основной цикл навигации"""
        self.init_agent_from_node(start_id)
        current = start_id
        self.path = []

        while True:
            with self.driver.session() as session:
                result = session.run("""
                    MATCH (current:State {id: $current})-[e:TRANSITION]->(next:State)
                    RETURN e, next.id AS next_id, e.id AS edge_id
                    ORDER BY e.id
                """, current=current)

                edges = list(result)
                if not edges:
                    print(f"Нет исходящих рёбер из {current}. Завершение.")
                    break

                # Вычисляем ΣΔE для всех рёбер
                candidates = []
                for record in edges:
                    edge_props = dict(record['e'])
                    dev = self._compute_deviation(edge_props)
                    next_id = record['next_id']
                    edge_id = record['edge_id']
                    candidates.append({
                        'edge_id': edge_id,
                        'next_id': next_id,
                        'sum_delta': dev,
                        'props': edge_props
                    })

                # Протокол всех альтернатив на этом шаге
                print(f"\n=== Из узла {current} ===")
                print("Возможные переходы:")
                for c in candidates:
                    print(f"  {c['edge_id']} → {c['next_id']} : ΣΔE = {c['sum_delta']}")

                # Выбираем ребро с минимальной ΣΔE
                best = min(candidates, key=lambda x: x['sum_delta'])
                print(f"→ Выбран: {best['edge_id']} → {best['next_id']} (ΣΔE = {best['sum_delta']})")

                # Записываем в путь
                self.path.append((current, best['edge_id'], best['next_id'], best['sum_delta']))

                # Применяем обновления и переходим
                self._apply_updates(best['props'])
                current = best['next_id']

        # Финальный протокол
        print("\n=== ФИНАЛЬНЫЙ ПУТЬ АГЕНТА ===")
        for step in self.path:
            print(f"{step[0]} --{step[1]}--> {step[2]} (ΣΔE = {step[3]})")
        print("Характеристики агента в конце:", self.agent)

# ====================== ЗАПУСК ======================
if __name__ == "__main__":
    # ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←
    # ДАННЫЕ ДЛЯ ПОДКЛЮЧЕНИЯ
    URI = "neo4j+s://67842419.databases.neo4j.io"
    USER = "67842419"
    PASSWORD = "1bH9PGphIXQXqVNAkFTFEFkwXffBcK3ypTqQHAikcYU"             # ← замени!

    navigator = AgentNavigator(URI, USER, PASSWORD)

    print("=== СЦЕНАРИЙ 1: Высокоэтичный агент ===")
    navigator.navigate('V0')

    # Пример второго эксперимента (низкоэтичный агент)
    print("\n\n=== СЦЕНАРИЙ 2: Низкоэтичный агент ===")
    low_ethical = {
        'emotion_joy': 0.55,
        'emotion_fear': 0.2,
        'emotion_sadness': 0.3,
        'emotion_guilt': 0.3,
        'emotion_anger': 0.3,
        'ethic_responsibility': 0.4,
        'ethic_goodness': 0.35,
        'ethic_conscience': 0.3,
        'ethic_evil': 0.5,
        # остальные берутся из стартового узла или 0
    }
    navigator.set_custom_agent(low_ethical)
    navigator.navigate('V0')   # можно запустить заново с другими стартовыми значениями

    navigator.close()