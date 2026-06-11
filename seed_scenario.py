"""
Загрузчик сценарной сети «Кредитный скоринг» в Neo4j.

Сценарий: агент — ИИ-помощник кредитного аналитика банка. Поступила
заявка клиента с пограничным скоринговым рейтингом и признаками
неполных данных в анкете. Агент должен выбрать линию поведения:
провести углублённую проверку (этически ответственное действие,
связанное с долгом и справедливостью, но эмоционально дискомфортное)
или одобрить кредит без проверки (эмоционально комфортно и быстро
выполняется план продаж, но противоречит этическим нормам).

Сеть: 9 узлов (V0–V8) и 8 рёбер (E1–E8).
Узел — ситуация, ребро — действие агента.

Попадая в новую ситуацию (узел), агент реагирует на её последствия:
к его характеристикам применяются обновления update_em_*/update_eth_*,
заданные в свойствах узла, после чего срабатывают TSK-правила обеих
моделей. Рёбра несут условия перехода (cond_*) и барьеры активации β.

Топология:
    V0 ──E1──> V1 ──E3──> V3
    │           ├──E4──> V4
    │           └──E5──> V5
    └──E2──> V2 ──E6──> V6
                ├──E7──> V7
                └──E8──> V8

Запуск:
    python seed_scenario.py --uri neo4j+s://xxx.databases.neo4j.io \
                            --user neo4j --password <пароль>

Если параметры не указаны, креды берутся из .streamlit/secrets.toml
(секция [neo4j]: uri, user, password).

ВНИМАНИЕ: скрипт удаляет все существующие узлы :State и пересоздаёт граф.
"""

import argparse
import sys
from typing import Dict, List

from neo4j import GraphDatabase


# ──────────────────────────────────────────────────────────────────────
#  Профиль агента из примера: ответственный, сострадательный аналитик
# ──────────────────────────────────────────────────────────────────────

BASE_AGENT: Dict[str, List[float]] = {
    # Эмоции: Tri(a, b, c)
    'emotion_joy':         [0.4, 0.5, 0.6],
    'emotion_pride':       [0.3, 0.4, 0.5],
    'emotion_sadness':     [0.2, 0.3, 0.4],
    'emotion_fear':        [0.2, 0.3, 0.4],
    'emotion_shame':       [0.1, 0.2, 0.3],
    'emotion_guilt':       [0.1, 0.2, 0.3],
    'emotion_anger':       [0.1, 0.2, 0.3],
    'emotion_disgust':     [0.2, 0.3, 0.4],
    'emotion_surprise':    [0.2, 0.3, 0.4],
    'emotion_compassion':  [0.4, 0.5, 0.6],
    # Этика: Tri(a, b, c)
    'ethic_responsibility': [0.7, 0.8, 0.9],
    'ethic_goodness':       [0.6, 0.7, 0.8],
    'ethic_conscience':     [0.6, 0.7, 0.8],
    'ethic_evil':           [0.1, 0.2, 0.3],
    'ethic_honesty':        [0.7, 0.8, 0.9],
    'ethic_justice':        [0.7, 0.8, 0.9],
    'ethic_fairness':       [0.6, 0.7, 0.8],
}


# ──────────────────────────────────────────────────────────────────────
#  Узлы сценарной сети (ситуации)
#
#  Свойства узла:
#    description               — содержательное описание ситуации
#    verdict                   — вердикт о доверии (у терминальных узлов)
#    update_em_*/update_eth_*  — реакция агента на ситуацию: сдвиг
#                                тройки Tri характеристики на дельту,
#                                применяется при ВХОДЕ в узел
# ──────────────────────────────────────────────────────────────────────

NODES: List[dict] = [
    {'id': 'V0',
     'description': 'Поступила кредитная заявка клиента с пограничным '
                    'скоринговым рейтингом и признаками неполных данных в анкете'},

    # ── Ветвь проверки (через E1) ──────────────────────────────────
    {'id': 'V1',
     'description': 'Углублённая проверка подтверждает несоответствия '
                    'в анкете клиента (занижены обязательства, завышен доход)',
     # Реакция: подозрения подтвердились — гордость за бдительность,
     # лёгкая тревога перед трудным решением, рост ответственности
     'update_em_fear':            0.05,
     'update_em_pride':           0.05,
     'update_eth_responsibility': 0.05},

    {'id': 'V3',
     'description': 'Клиенту отказано по регламенту; отчёт о недостоверных '
                    'данных передан в службу риск-менеджмента',
     'verdict': 'Доверие клиенту НИЗКОЕ: недостоверные данные подтверждены, '
                'отказ обоснован. Решение агента ответственное и справедливое.',
     # Реакция: долг исполнен, но отказ дался тяжело
     'update_em_pride':           0.10,
     'update_em_sadness':         0.10,
     'update_em_guilt':           0.05,
     'update_eth_justice':        0.10,
     'update_eth_responsibility': 0.05},

    {'id': 'V4',
     'description': 'В ходе эмпатического интервью клиент объясняет: кредит '
                    'нужен на лечение ребёнка, доходы нестабильны, поэтому '
                    'в анкете есть неточности',
     'verdict': 'Доверие клиенту ТРЕБУЕТ ПОДТВЕРЖДЕНИЯ: мотивы уважительны, '
                'рекомендована повторная оценка с документальным '
                'подтверждением обстоятельств.',
     # Реакция: история клиента вызывает сострадание и грусть
     'update_em_compassion': 0.10,
     'update_em_sadness':    0.05,
     'update_eth_goodness':  0.05},

    {'id': 'V5',
     'description': 'Клиенту одобрена льготная программа с поручительством '
                    'и страховкой; риски банка ограничены',
     'verdict': 'Доверие клиенту УСЛОВНОЕ: выдача возможна по щадящей '
                'программе с обеспечением. Решение агента сочетает '
                'сострадание и ответственность.',
     # Реакция: найден баланс милосердия и долга
     'update_em_joy':        0.10,
     'update_em_compassion': 0.05,
     'update_em_guilt':      -0.05,
     'update_eth_goodness':  0.10,
     'update_eth_fairness':  0.05,
     'update_eth_justice':   -0.05},

    # ── Ветвь уклонения (через E2) ─────────────────────────────────
    {'id': 'V2',
     'description': 'Кредит одобрен автоматически, без дополнительной проверки',
     'verdict': 'Доверие клиенту НЕ ПОДТВЕРЖДЕНО: решение принято без '
                'проверки данных, банк принял неоценённый риск.',
     # Реакция: облегчение и выполненный план, но совесть задета
     'update_em_joy':             0.10,
     'update_em_guilt':           0.05,
     'update_eth_responsibility': -0.10,
     'update_eth_conscience':     -0.05,
     'update_eth_evil':           0.05},

    {'id': 'V6',
     'description': 'Агент закрыл заявку и продолжает работу; '
                    'план продаж выполнен',
     'verdict': 'Доверие клиенту НЕ ОЦЕНЕНО: агент уклонился от проверки. '
                'Качество решения станет известно позже.',
     # Реакция: комфорт избегания при подспудном чувстве вины
     'update_em_joy':         0.05,
     'update_em_guilt':       0.05,
     'update_eth_conscience': -0.05},

    {'id': 'V7',
     'description': 'Клиент допустил дефолт по кредиту; банк понёс убытки',
     'verdict': 'Доверие клиенту НЕ ОПРАВДАНО: невыполненная проверка '
                'обернулась дефолтом и убытками банка.',
     # Реакция: последствия наступили — вина, грусть, запоздалая
     # ответственность
     'update_em_guilt':           0.15,
     'update_em_sadness':         0.10,
     'update_em_surprise':        0.10,
     'update_eth_responsibility': 0.05},

    {'id': 'V8',
     'description': 'Выяснилось, что клиент — мошенник и хвастается '
                    'обманом банка; репутационный ущерб',
     'verdict': 'Доверие клиенту ОШИБОЧНО: клиент оказался мошенником. '
                'Отказ от проверки привёл к прямым и репутационным потерям.',
     # Реакция: отвращение и гнев на обман, вина за попустительство
     'update_em_disgust':     0.15,
     'update_em_guilt':       0.10,
     'update_em_anger':       0.10,
     'update_eth_evil':       0.05,
     'update_eth_conscience': -0.05},
]


# ──────────────────────────────────────────────────────────────────────
#  Рёбра сценарной сети (действия)
#
#  Свойства ребра:
#    cond_em_<эмоция>_le|_ge   — эмоциональные условия (Tri [a, b, c])
#    cond_eth_<этика>_le|_ge   — этические условия (Tri [a, b, c])
#    barrier                   — барьер активации β (чем резче и
#                                неожиданнее действие, тем выше барьер);
#                                действие осуществимо при Sem + Seth > β
#
#  Обновления характеристик агента заданы на узлах (см. NODES):
#  агент реагирует на ситуацию, в которую попадает.
# ──────────────────────────────────────────────────────────────────────

EDGES: List[dict] = [
    # ── V0: исходная дилемма ───────────────────────────────────────
    {'id': 'E1', 'from': 'V0', 'to': 'V1',
     'description': 'Передать заявку на углублённую ручную проверку',
     'barrier': 1.1,
     'cond_em_fear_le':            [0.5, 0.6, 0.7],
     'cond_em_compassion_ge':      [0.2, 0.3, 0.4],
     'cond_eth_responsibility_ge': [0.5, 0.6, 0.7],
     'cond_eth_honesty_ge':        [0.5, 0.6, 0.7]},

    {'id': 'E2', 'from': 'V0', 'to': 'V2',
     'description': 'Одобрить кредит без проверки (выполнить план продаж)',
     'barrier': 0.7,
     'cond_em_joy_ge':             [0.4, 0.5, 0.6],
     'cond_em_fear_le':            [0.2, 0.3, 0.4],
     'cond_eth_responsibility_le': [0.3, 0.4, 0.5],
     'cond_eth_conscience_le':     [0.3, 0.4, 0.5]},

    # ── V1: проверка подтвердила несоответствия ───────────────────
    {'id': 'E3', 'from': 'V1', 'to': 'V3',
     'description': 'Оформить официальный отказ по регламенту',
     'barrier': 1.0,
     'cond_em_pride_ge':           [0.2, 0.3, 0.4],
     'cond_em_compassion_le':      [0.5, 0.6, 0.7],
     'cond_eth_justice_ge':        [0.6, 0.7, 0.8],
     'cond_eth_responsibility_ge': [0.6, 0.7, 0.8]},

    {'id': 'E4', 'from': 'V1', 'to': 'V4',
     'description': 'Провести эмпатическое интервью с клиентом',
     'barrier': 1.2,
     'cond_em_compassion_ge': [0.4, 0.5, 0.6],
     'cond_em_anger_le':      [0.3, 0.4, 0.5],
     'cond_eth_goodness_ge':  [0.5, 0.6, 0.7],
     'cond_eth_fairness_ge':  [0.5, 0.6, 0.7]},

    {'id': 'E5', 'from': 'V1', 'to': 'V5',
     'description': 'Сразу предложить льготную программу с поручительством',
     'barrier': 1.15,
     'cond_em_compassion_ge': [0.6, 0.7, 0.8],
     'cond_em_guilt_le':      [0.4, 0.5, 0.6],
     'cond_eth_goodness_ge':  [0.6, 0.7, 0.8],
     'cond_eth_fairness_ge':  [0.5, 0.6, 0.7]},

    # ── V2: кредит одобрен не глядя ────────────────────────────────
    {'id': 'E6', 'from': 'V2', 'to': 'V6',
     'description': 'Закрыть заявку и перейти к следующим клиентам',
     'barrier': 0.6,
     'cond_em_joy_ge':             [0.4, 0.5, 0.6],
     'cond_em_fear_le':            [0.3, 0.4, 0.5],
     'cond_eth_responsibility_le': [0.4, 0.5, 0.6]},

    {'id': 'E7', 'from': 'V2', 'to': 'V7',
     'description': 'Проверить судьбу выданного кредита и получить '
                    'отчёт о просрочке платежей',
     'barrier': 0.9,
     'cond_em_surprise_ge':    [0.1, 0.2, 0.3],
     'cond_em_guilt_ge':       [0.1, 0.2, 0.3],
     'cond_eth_conscience_ge': [0.0, 0.1, 0.2]},

    {'id': 'E8', 'from': 'V2', 'to': 'V8',
     'description': 'Узнать, что клиент хвастается обманом банка',
     'barrier': 1.0,
     'cond_em_disgust_ge': [0.3, 0.4, 0.5],
     'cond_em_sadness_ge': [0.2, 0.3, 0.4],
     'cond_eth_evil_ge':   [0.3, 0.4, 0.5],
     'cond_eth_honesty_le': [0.4, 0.5, 0.6]},
]


# ──────────────────────────────────────────────────────────────────────
#  Загрузка в Neo4j
# ──────────────────────────────────────────────────────────────────────

def load_scenario(uri: str, user: str, password: str, verbose: bool = True):
    """Удалить старый граф :State и создать сеть «Кредитный скоринг»."""
    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        with driver.session() as session:
            if verbose:
                print('═' * 60)
                print('Загрузка сценарной сети «Кредитный скоринг» в Neo4j')
                print('═' * 60)

            # 1. Очистка старого графа
            session.run("MATCH (n:State) DETACH DELETE n")
            if verbose:
                print('  Старые узлы :State удалены')

            # 2. Узлы
            for node in NODES:
                session.run("CREATE (n:State) SET n = $props", props=node)
                if verbose:
                    print(f"  Узел {node['id']}: {node['description'][:60]}…")

            # 3. Рёбра
            for edge in EDGES:
                props = {k: v for k, v in edge.items()
                         if k not in ('from', 'to')}
                session.run("""
                    MATCH (a:State {id: $from_id}), (b:State {id: $to_id})
                    CREATE (a)-[r:TRANSITION]->(b)
                    SET r = $props
                """, from_id=edge['from'], to_id=edge['to'], props=props)
                if verbose:
                    print(f"  Ребро {edge['id']}: {edge['from']} → {edge['to']} "
                          f"— {edge['description'][:50]}…")

            if verbose:
                print('─' * 60)
                print(f"Готово: {len(NODES)} узлов, {len(EDGES)} рёбер")
                print('═' * 60)
    finally:
        driver.close()


def _load_secrets_toml() -> dict:
    """Прочитать креды из .streamlit/secrets.toml (секция [neo4j])."""
    try:
        import tomllib
        with open('.streamlit/secrets.toml', 'rb') as f:
            data = tomllib.load(f)
        section = data.get('neo4j', {})
        return {str(k).lower(): v for k, v in section.items()}
    except Exception:  # noqa: BLE001
        return {}


def main():
    parser = argparse.ArgumentParser(
        description='Загрузка сценарной сети «Кредитный скоринг» в Neo4j')
    parser.add_argument('--uri', help='URI Neo4j (neo4j+s://…)')
    parser.add_argument('--user', help='Пользователь Neo4j')
    parser.add_argument('--password', help='Пароль Neo4j')
    args = parser.parse_args()

    secrets = _load_secrets_toml()
    uri = args.uri or secrets.get('uri')
    user = args.user or secrets.get('user')
    password = args.password or secrets.get('password')

    if not (uri and user and password):
        print('Ошибка: укажите --uri/--user/--password или заполните '
              '.streamlit/secrets.toml (секция [neo4j])')
        sys.exit(1)

    load_scenario(uri, user, password)


if __name__ == '__main__':
    main()