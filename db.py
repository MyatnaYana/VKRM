from neo4j import GraphDatabase

class Neo4jConnector:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def get_node_characteristics(self, node_id):
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (n:Node {id:$id})
                RETURN 
                  n.emotion_joy AS joy,
                  n.emotion_pride AS pride,
                  n.emotion_fear AS fear,
                  n.emotion_sadness AS sadness,
                  n.emotion_shame AS shame,
                  n.emotion_guilt AS guilt,
                  n.emotion_anger AS anger,
                  n.ethic_responsibility AS responsibility,
                  n.ethic_goodness AS goodness,
                  n.ethic_conscience AS conscience,
                  n.ethic_evil AS evil
                """,
                id=node_id
            ).single()
            if result:
                emotions = {k: result[k] for k in ["joy","pride","fear","sadness","shame","guilt","anger"]}
                ethics = {k: result[k] for k in ["responsibility","goodness","conscience","evil"]}
                return emotions, ethics
            else:
                return None, None

    def get_outgoing_edges(self, node_id):
        with self.driver.session() as session:
            results = session.run(
                """
                MATCH (n:Node {id:$id})-[r]->(m:Node)
                RETURN type(r) AS edge_type, r.description AS description, r AS props, m.id AS target
                """,
                id=node_id
            )
            edges = []
            for record in results:
                edges.append({
                    "type": record["edge_type"],
                    "description": record["description"],
                    "props": dict(record["props"]),
                    "target": record["target"]
                })
            return edges
