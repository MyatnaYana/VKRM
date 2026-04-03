MATCH path = (start:State {id: 'V0'})-[*]->(end)
WHERE end.id IN ['V3', 'V6']  // конечные узлы из твоих экспериментов

// Выбранный путь (замени на реальный)
WITH path,
     CASE 
       WHEN [r IN relationships(path) | r.id] = ['E1', 'E3'] THEN true 
       ELSE false 
     END AS is_chosen

RETURN path,
       is_chosen,
       "Зелёный = выбранный путь агента" AS legend