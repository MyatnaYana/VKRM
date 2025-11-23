# db.py
from neo4j import GraphDatabase

class Neo4jConnector:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def get_outgoing_edges(self, node_id):
        """
        Возвращает список исходящих ребер с условиями эмоций и этики
        """
        query = """
        MATCH (n:Node {id: $node_id})-[r]->(m:Node)
        RETURN m.id AS to, r.description AS description,
               r.cond_em_joy AS em_joy, r.cond_em_pride AS em_pride,
               r.cond_em_fear AS em_fear, r.cond_em_sadness AS em_sadness,
               r.cond_em_shame AS em_shame, r.cond_em_guilt AS em_guilt,
               r.cond_em_anger AS em_anger,
               r.cond_eth_responsibility AS eth_responsibility,
               r.cond_eth_goodness AS eth_goodness,
               r.cond_eth_conscience AS eth_conscience,
               r.cond_eth_evil AS eth_evil
        """
        edges = []
        with self.driver.session() as session:
            results = session.run(query, node_id=node_id)
            for record in results:
                cond_em = {}
                cond_eth = {}
                # эмоции
                for key in ['joy','pride','fear','sadness','shame','guilt','anger']:
                    val = record.get(f"em_{key}")
                    if val is not None:
                        cond_em[key] = val
                # этика
                for key in ['responsibility','goodness','conscience','evil']:
                    val = record.get(f"eth_{key}")
                    if val is not None:
                        cond_eth[key] = val
                edges.append({
                    'to': record['to'],
                    'description': record['description'],
                    'cond_em': cond_em,
                    'cond_eth': cond_eth
                })
        return edges

    def get_node_updates(self, node_id):
        """
        Возвращает обновления характеристик после перехода на узел
        """
        query = """
        MATCH (n:Node {id:$node_id})
        RETURN n.update_joy AS joy,
               n.update_pride AS pride,
               n.update_fear AS fear,
               n.update_sadness AS sadness,
               n.update_shame AS shame,
               n.update_guilt AS guilt,
               n.update_anger AS anger,
               n.update_responsibility AS responsibility,
               n.update_goodness AS goodness,
               n.update_conscience AS conscience,
               n.update_evil AS evil
        """
        updates = {'emotions': {}, 'ethics': {}}
        with self.driver.session() as session:
            record = session.run(query, node_id=node_id).single()
            if record:
                # эмоции
                for key in ['joy','pride','fear','sadness','shame','guilt','anger']:
                    val = record.get(key)
                    if val is not None:
                        updates['emotions'][key] = val
                # этика
                for key in ['responsibility','goodness','conscience','evil']:
                    val = record.get(key)
                    if val is not None:
                        updates['ethics'][key] = val
        return updates
