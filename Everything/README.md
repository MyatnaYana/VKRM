***Можно работать с graphviz напрямую создавая .dot файл***

dot -Tpng filename.dot -o graph.png

-Tpng: формат выходного файла (можно выбрать svg, pdf, jpg, и т. д.).

-o: имя выходного файла

Для интеграции с Python скачиваем pip install graphviz

Полезные параметры DOT:

  Узлы:
  
A [label="Start Node", shape=box, color=red];

label: текст внутри узла.

shape: форма узла (например, circle, box, ellipse).

color: цвет узла.

  Рёбра:
  
A -> B [label="Edge Label", color=blue, style=dashed];

label: текст на ребре.

color: цвет ребра.

style: стиль (например, dashed, dotted, bold).
