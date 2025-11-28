# Шпаргалка по командам и коду

```
# Create a single node
with driver.session() as session:
    result = session.run("""
        CREATE (e:Employee {
            employee_id: $employee_id,
            first_name: $first_name,
            last_name: $last_name,
            email: $email,
            department: $department,
            salary: $salary
        })
        RETURN e
    """, employee_id="EMP001", first_name="John", last_name="Doe",
         email="john@company.com", department="Engineering", salary=75000)
    
    record = result.single()
    print(f"Created node: {record['e']}")
```

```
# Create multiple nodes
employees = [
    {"id": "EMP001", "name": "John Doe", "dept": "Engineering"},
    {"id": "EMP002", "name": "Jane Smith", "dept": "Marketing"},
    {"id": "EMP003", "name": "Bob Johnson", "dept": "Sales"}
]

with driver.session() as session:
    for emp in employees:
        session.run("""
            CREATE (e:Employee {
                employee_id: $id,
                name: $name,
                department: $dept
            })
        """, id=emp["id"], name=emp["name"], dept=emp["dept"])
    
    print(f"Created {len(employees)} employee nodes")
```

```
with driver.session() as session:
    # Create two nodes and relationship
    session.run("""
        CREATE (e1:Employee {employee_id: 'EMP001', name: 'John Doe'})
        CREATE (e2:Employee {employee_id: 'EMP002', name: 'Jane Smith'})
        CREATE (e1)-[:REPORTS_TO {since: date('2024-01-01')}]->(e2)
    """)
    
    print("Nodes and relationship created!")
    
    # Create relationship between existing nodes
    session.run("""
        MATCH (e1:Employee {employee_id: 'EMP003'})
        MATCH (e2:Employee {employee_id: 'EMP002'})
        CREATE (e1)-[:WORKS_WITH {project: 'ProjectX'}]->(e2)
    """)
    
    print("Relationship created between existing nodes!")
```


```
with driver.session() as session:
    # Find all employee nodes
    result = session.run("""
        MATCH (e:Employee)
        RETURN e.employee_id, e.name, e.department
        ORDER BY e.name
```