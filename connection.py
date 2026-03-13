from neo4j import GraphDatabase

# URI examples: "neo4j://localhost", "neo4j+s://xxx.databases.neo4j.io"
URI = "neo4j+s://53488742.databases.neo4j.io"
AUTH = ("<username>", "<password>")

with GraphDatabase.driver(URI, auth=AUTH) as driver:
    driver.verify_connectivity()