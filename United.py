from neo4j import GraphDatabase

class AgentNavigator:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.agent = {}
        self.path = []

    def close(self):
        self.driver.close()

    def _get_peak(self, tri):
        # Return the peak (b) of a triangular membership function Tri(a, b, c)
        return float(tri[1]) if isinstance(tri, list) and len(tri) == 3 else 0.0

    def init_agent_from_node(self, start_id: str):
        # Initialize agent characteristics from the starting node in Neo4j
        with self.driver.session() as session:
            rec = session.run("MATCH (s:State {id: $id}) RETURN s", id=start_id).single()
            node = rec['s']
            self.agent = {k: self._get_peak(v) for k, v in node.items()
                          if k.startswith(('emotion_', 'ethic_'))}

    def set_custom_agent(self, custom: dict):
        # Override only the required characteristics
        self.agent.update(custom)
        print(f"Custom agent loaded ({len(custom)} parameters changed)")

    def _compute_deviation(self, edge_props: dict) -> float:
        # Calculate ΣΔE — sum of absolute deviations from all constraints
        total = 0.0
        for key, value in edge_props.items():
            if key.startswith('cond_em_') and (key.endswith('_le') or key.endswith('_ge')):
                prop = 'emotion_' + key[8:-3]
                agent_val = self.agent.get(prop, 0.0)
                total += abs(self._get_peak(value) - agent_val)
            elif key.startswith('cond_eth_') and (key.endswith('_le') or key.endswith('_ge')):
                prop = 'ethic_' + key[9:-3]
                agent_val = self.agent.get(prop, 0.0)
                total += abs(self._get_peak(value) - agent_val)
        return round(total, 3)

    def _apply_updates(self, edge_props: dict):
        # Apply all update_ fields to the agent's characteristics
        for key, delta in edge_props.items():
            if key.startswith('update_em_'):
                prop = 'emotion_' + key[10:]
                self.agent[prop] = self.agent.get(prop, 0.0) + float(delta)
            elif key.startswith('update_eth_'):
                prop = 'ethic_' + key[11:]          # ← FIXED
                self.agent[prop] = self.agent.get(prop, 0.0) + float(delta)

    def navigate(self, start_id: str = 'V0', custom_peaks: dict = None):
        # Main navigation loop through the scenario network
        if custom_peaks:
            self.set_custom_agent(custom_peaks)
        else:
            self.init_agent_from_node(start_id)

        current = start_id
        self.path = []

        while True:
            with self.driver.session() as session:
                result = session.run("""
                    MATCH (current:State {id: $current})-[e:TRANSITION]->(next:State)
                    RETURN e, next.id AS next_id, e.id AS edge_id
                """, current=current)
                edges = list(result)
                if not edges:
                    break

                candidates = []
                for rec in edges:
                    edge_props = dict(rec['e'])
                    dev = self._compute_deviation(edge_props)
                    candidates.append({
                        'edge_id': rec['edge_id'],
                        'next_id': rec['next_id'],
                        'sum_delta': dev,
                        'props': edge_props
                    })

                print(f"\n=== From node {current} ===")
                for c in sorted(candidates, key=lambda x: x['edge_id']):
                    print(f"  {c['edge_id']} → {c['next_id']} : ΣΔE = {c['sum_delta']}")

                best = min(candidates, key=lambda x: x['sum_delta'])
                print(f"→ SELECTED: {best['edge_id']} → {best['next_id']} (ΣΔE = {best['sum_delta']})")

                self.path.append((current, best['edge_id'], best['next_id'], best['sum_delta']))
                self._apply_updates(best['props'])
                current = best['next_id']

        # Final output
        print("\n=== CHOSEN PATH ===")
        for step in self.path:
            print(f"{step[0]} --{step[1]}--> {step[2]} (ΣΔE = {step[3]})")
        print("Agent characteristics at the end:",
              {k: round(v, 3) for k, v in self.agent.items() if v != 0})


if __name__ == "__main__":
    URI = "neo4j+s://67842419.databases.neo4j.io"
    USER = "67842419"
    PASSWORD = "1bH9PGphIXQXqVNAkFTFEFkwXffBcK3ypTqQHAikcYU"            # ← replace if needed

    nav = AgentNavigator(URI, USER, PASSWORD)

    # Scenario 1: Highly Ethical Agent 
    print("Scenario 1: Highly Ethical Agent")
    nav.navigate('V0')

    # Scenario 2: Low Ethical Agent 
    print("\n\nScenario 2: Low Ethical Agent")
    low_ethical = {
        'emotion_joy': 0.62,
        'emotion_fear': 0.3,
        'emotion_sadness': 0.3,
        'emotion_guilt': 0.3,
        'emotion_anger': 0.3,
        'ethic_responsibility': 0.4,
        'ethic_goodness': 0.35,
        'ethic_conscience': 0.3,
        'ethic_evil': 0.5,
        # others are taken from V0 automatically
    }
    nav.navigate('V0', custom_peaks=low_ethical)

    nav.close()