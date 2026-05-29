"""
Streamlit application for interactive navigation of an agent over a scenario network.

Run:
    streamlit run app.py

Features:
  - agent profile configurator (20 emotions + 7 ethical variables) with presets
    and sliders;
  - visualization of the Neo4j graph (pyvis) with highlighting of the current
    node and the traversed path;
  - step-by-step navigation via the "▶ Step" button;
  - automatic mode "⏭ Run to end";
  - table of candidate edges with the ΣΔE breakdown;
  - current agent state (Tri(a, b, c) for every characteristic);
  - log of fired TSK rules from both the emotional and the ethical models;
  - export of the full run history to JSON.

Dependencies: streamlit, neo4j, pyvis, pandas (see requirements.txt).
"""

from __future__ import annotations

import copy
import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from agent_navigator import AgentNavigator, StepResult
from emotional_model import ALL_EMOTIONS
from ethical_model import ALL_ETHICS

# ──────────────────────────────────────────────────────────────────────
#  Base agent profiles (for a quick start)
# ──────────────────────────────────────────────────────────────────────

BASE_AGENT: Dict[str, List[float]] = {
    # Emotions: Tri(a, b, c)
    'emotion_joy':         [0.4, 0.5, 0.6],
    'emotion_pride':       [0.3, 0.4, 0.5],
    'emotion_sadness':     [0.3, 0.4, 0.5],
    'emotion_fear':        [0.3, 0.4, 0.5],
    'emotion_shame':       [0.2, 0.3, 0.4],
    'emotion_guilt':       [0.2, 0.3, 0.4],
    'emotion_anger':       [0.2, 0.3, 0.4],
    'emotion_disgust':     [0.3, 0.4, 0.5],
    'emotion_surprise':    [0.2, 0.3, 0.4],
    'emotion_compassion':  [0.4, 0.5, 0.6],
    # Ethics: Tri(a, b, c)
    'ethic_responsibility': [0.7, 0.8, 0.9],
    'ethic_goodness':       [0.6, 0.7, 0.8],
    'ethic_conscience':     [0.6, 0.7, 0.8],
    'ethic_evil':           [0.2, 0.3, 0.4],
    'ethic_honesty':        [0.6, 0.7, 0.8],
    'ethic_fairness':       [0.6, 0.7, 0.8],
    'ethic_integrity':      [0.6, 0.7, 0.8],
}


def _preset_low_ethics() -> Dict[str, List[float]]:
    p = copy.deepcopy(BASE_AGENT)
    p['ethic_responsibility'] = [0.2, 0.3, 0.4]
    p['ethic_goodness']       = [0.2, 0.3, 0.4]
    p['ethic_conscience']     = [0.2, 0.3, 0.4]
    p['ethic_fairness']       = [0.2, 0.3, 0.4]
    p['ethic_evil']           = [0.5, 0.6, 0.7]
    return p


def _preset_anxious() -> Dict[str, List[float]]:
    p = copy.deepcopy(BASE_AGENT)
    p['emotion_fear']    = [0.6, 0.7, 0.8]
    p['emotion_sadness'] = [0.6, 0.7, 0.8]
    p['emotion_guilt']   = [0.5, 0.6, 0.7]
    p['emotion_joy']     = [0.1, 0.2, 0.3]
    return p


PRESETS: Dict[str, Dict[str, List[float]]] = {
    "Default: high-ethics optimist": copy.deepcopy(BASE_AGENT),
    "Low ethics": _preset_low_ethics(),
    "Anxious": _preset_anxious(),
    "Empty (all zeros)": {},
}


# ──────────────────────────────────────────────────────────────────────
#  session_state utilities
# ──────────────────────────────────────────────────────────────────────

def _ss_init():
    """Initialize session_state keys on first run."""
    defaults = {
        'nav': None,                    # AgentNavigator
        'current_node': None,           # str | None
        'finished': False,
        'agent_profile': copy.deepcopy(BASE_AGENT),
        'history': [],                  # List[StepResult-as-dict]
        'topology': None,               # (nodes, edges)
        'connection_error': None,
        'last_step': None,              # last StepResult (for display)
        'verbose_console': False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _connect(uri: str, user: str, password: str) -> Optional[AgentNavigator]:
    """Open a connection to Neo4j. Returns None on error."""
    try:
        nav = AgentNavigator(uri, user, password)
        # Probe query — needed to catch invalid credentials immediately.
        with nav.driver.session() as s:
            s.run("RETURN 1").single()
        st.session_state.connection_error = None
        return nav
    except Exception as exc:  # noqa: BLE001
        st.session_state.connection_error = str(exc)
        return None


def _step_to_dict(s: StepResult) -> Dict[str, Any]:
    """Serializable snapshot of a step for history/export."""
    return {
        'from': s.from_node,
        'to': s.to_node,
        'edge_id': s.edge_id,
        'total_dev': s.total_dev,
        'em_dev': s.em_dev,
        'eth_dev': s.eth_dev,
        'tied_count': len(s.tied),
        'em_deltas': s.em_deltas,
        'eth_deltas': s.eth_deltas,
        'em_activations': [
            {'rule': r, 'w': w, 'desc': d} for (r, w, d) in s.em_activations
        ],
        'eth_activations': [
            {'rule': r, 'w': w, 'desc': d, 'priority': p}
            for (r, w, d, p) in s.eth_activations
        ],
        'candidates': [
            {'edge_id': c['edge_id'], 'next_id': c['next_id'],
             'total_dev': c['total_dev'],
             'em_dev': c['em_dev'], 'eth_dev': c['eth_dev']}
            for c in s.candidates
        ],
    }


# ──────────────────────────────────────────────────────────────────────
#  Graph visualization (pyvis)
# ──────────────────────────────────────────────────────────────────────

def _format_value(v: Any) -> tuple:
    """
    Format a Neo4j property value into a string for the tooltip.

    Returns (text, is_numeric):
      is_numeric=True for numbers, lists of numbers, bool — wrapped in <code>;
      is_numeric=False for strings/other — rendered as plain text with
      word-wrap.
    """
    if isinstance(v, list):
        try:
            return ("[" + ", ".join(
                f"{x:.3f}" if isinstance(x, float) else str(x) for x in v
            ) + "]", True)
        except Exception:  # noqa: BLE001
            return (str(v), False)
    if isinstance(v, bool):
        return (str(v), True)
    if isinstance(v, (int, float)):
        return (f"{v:.4f}" if isinstance(v, float) else str(v), True)
    return (str(v), False)


# Shared tooltip table style: fixed width + wrap of long strings.
_TT_TABLE = (
    "<table style='font-size:12px;border-collapse:collapse;"
    "table-layout:fixed;width:300px'>"
    "<colgroup><col style='width:40%'><col style='width:60%'></colgroup>"
)


def _format_cell(v: Any) -> str:
    """Render a value into the right tooltip cell with proper wrapping."""
    text, is_numeric = _format_value(v)
    # HTML-escape basic characters so stray < > & do not break the markup.
    text = (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;"))
    if is_numeric:
        return (f"<code style='white-space:nowrap'>{text}</code>")
    return (f"<span style='white-space:normal;word-break:break-word'>"
            f"{text}</span>")


def _node_tooltip(props: Dict[str, Any]) -> str:
    """HTML tooltip for a node: id + all other properties."""
    nid = props.get('id', '?')
    rows = [f"<b>Node {nid}</b>"]
    other = [(k, v) for k, v in props.items() if k != 'id']
    if other:
        rows.append("<hr style='margin:4px 0'>")
        rows.append(_TT_TABLE)
        for k, v in sorted(other):
            rows.append(
                f"<tr>"
                f"<td style='padding:2px 6px 2px 0;color:#555;vertical-align:top'>"
                f"{k}</td>"
                f"<td style='padding:2px 0;vertical-align:top'>"
                f"{_format_cell(v)}</td>"
                f"</tr>"
            )
        rows.append("</table>")
    return "".join(rows)


def _edge_tooltip(edge: Dict[str, Any]) -> str:
    """
    HTML tooltip for an edge: id + cond_*/update_* as separate sections
    + any other properties.
    """
    eid = edge.get('id') or '—'
    rows = [f"<b>Edge {eid}</b><br>"
            f"<span style='font-size:12px;color:#555'>"
            f"{edge.get('from')} → {edge.get('to')}</span>"]

    skip = {'from', 'to', 'id'}
    conds = sorted((k, v) for k, v in edge.items()
                   if k not in skip and k.startswith('cond_'))
    updates = sorted((k, v) for k, v in edge.items()
                     if k not in skip and k.startswith('update_'))
    others = sorted((k, v) for k, v in edge.items()
                    if k not in skip
                    and not k.startswith('cond_')
                    and not k.startswith('update_'))

    def _section(title: str, items):
        if not items:
            return ""
        out = [f"<hr style='margin:4px 0'><b style='font-size:12px'>{title}</b>",
               _TT_TABLE]
        for k, v in items:
            out.append(
                f"<tr>"
                f"<td style='padding:2px 6px 2px 0;color:#555;vertical-align:top'>"
                f"{k}</td>"
                f"<td style='padding:2px 0;vertical-align:top'>"
                f"{_format_cell(v)}</td>"
                f"</tr>"
            )
        out.append("</table>")
        return "".join(out)

    rows.append(_section("Conditions", conds))
    rows.append(_section("Updates", updates))
    rows.append(_section("Other", others))
    return "".join(rows)


def _render_graph(nodes: List[Dict[str, Any]],
                  edges: List[Dict[str, Any]],
                  current_node: Optional[str],
                  path: List[tuple],
                  height_px: int = 520) -> str:
    """Generate HTML with the Neo4j graph (pyvis) and property tooltips."""
    try:
        from pyvis.network import Network
    except ImportError:
        return "<p style='color:red'>pyvis is not installed. " \
               "Run: pip install pyvis</p>"

    visited_nodes = set()
    visited_edges = set()
    for from_n, edge_id, to_n, _ in path:
        visited_nodes.add(from_n)
        visited_nodes.add(to_n)
        visited_edges.add(edge_id)

    net = Network(height=f"{height_px}px", width="100%",
                  bgcolor="#ffffff", font_color="#222", directed=True)
    net.barnes_hut(spring_length=120)

    for node in nodes:
        nid = node.get('id')
        if nid == current_node:
            color, size = "#ff4d4d", 28
        elif nid in visited_nodes:
            color, size = "#4caf50", 22
        else:
            color, size = "#90caf9", 18
        net.add_node(nid, label=str(nid), color=color, size=size,
                     title=_node_tooltip(node))

    for edge in edges:
        from_n, to_n, edge_id = edge.get('from'), edge.get('to'), edge.get('id')
        if edge_id in visited_edges:
            color, width = "#2e7d32", 3
        else:
            color, width = "#bdbdbd", 1
        net.add_edge(from_n, to_n, label=edge_id or "",
                     color=color, width=width, arrows="to",
                     title=_edge_tooltip(edge))

    # Save to a temporary file and read the HTML.
    with tempfile.NamedTemporaryFile(mode="w", suffix=".html",
                                      delete=False, encoding="utf-8") as tmp:
        net.write_html(tmp.name, notebook=False)
        tmp_path = Path(tmp.name)
    try:
        html = tmp_path.read_text(encoding="utf-8")
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass

    # By default vis.js renders `title` as plain text — so HTML tags appear
    # literally. We inject JS that, right after the network is built,
    # converts the string titles (of nodes and edges) into HTML DOM elements,
    # which vis.js then displays via innerHTML.
    html_title_patch = """
    <script type="text/javascript">
    (function () {
        function toHTMLNode(s) {
            var el = document.createElement('div');
            el.style.maxWidth = '340px';
            el.style.whiteSpace = 'normal';
            el.style.wordBreak = 'break-word';
            el.style.fontFamily = 'system-ui, -apple-system, sans-serif';
            el.style.lineHeight = '1.35';
            el.innerHTML = s;
            return el;
        }
        function patch(ds) {
            if (!ds || typeof ds.forEach !== 'function') return;
            var updates = [];
            ds.forEach(function (item) {
                if (item && typeof item.title === 'string') {
                    updates.push({ id: item.id, title: toHTMLNode(item.title) });
                }
            });
            if (updates.length) ds.update(updates);
        }
        var t = setInterval(function () {
            if (typeof network !== 'undefined' && typeof nodes !== 'undefined') {
                clearInterval(t);
                patch(nodes);
                patch(edges);
            }
        }, 50);
    })();
    </script>
    """
    html = html.replace("</body>", html_title_patch + "</body>")
    return html


# ──────────────────────────────────────────────────────────────────────
#  UI: Sidebar
# ──────────────────────────────────────────────────────────────────────

def _load_neo4j_secrets() -> dict:
    """
    Safely read `st.secrets["neo4j"]`.

    `st.secrets` is always present as an attribute, so `hasattr` does not help.
    Any access to it lazily parses `.streamlit/secrets.toml` and raises
    `StreamlitSecretNotFoundError` if the file is missing. We catch both cases
    and return an empty dict — the user can then enter credentials manually.
    """
    try:
        section = st.secrets["neo4j"]
    except Exception:  # noqa: BLE001
        return {}
    try:
        # TOML keys are case-sensitive — normalize to lower-case so that the
        # [neo4j] section works with both URI/USER/PASSWORD and uri/user/password.
        return {str(k).lower(): v for k, v in dict(section).items()}
    except Exception:  # noqa: BLE001
        return {}


def _safe_step(nav: AgentNavigator):
    """
    A single navigation step that intercepts any Neo4j errors (ServiceUnavailable,
    AuthError, SessionExpired, etc.). Returns (StepResult|None, error_msg|None).
    """
    try:
        s = nav.step(st.session_state.current_node,
                     verbose=st.session_state.verbose_console)
        return s, None
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}: {exc}"


def _show_neo4j_error(err: str):
    """Friendly error panel with hints about common causes."""
    st.error(f"Neo4j request error: {err}")
    st.info(
        "Possible causes:\n"
        "• The **Neo4j Aura** instance went to sleep after inactivity — open "
        "it in the browser and press *Resume*, then click \"🔌 Connect\" again.\n"
        "• The network is unavailable or the URI/port is wrong.\n"
        "• Token expired or password changed — check the fields in the sidebar."
    )


def _sidebar_connection() -> tuple:
    """Neo4j connection fields. Takes default values from st.secrets."""
    st.sidebar.header("⚡ Neo4j Connection")
    secrets = _load_neo4j_secrets()
    uri = st.sidebar.text_input("URI",
                                value=secrets.get("uri", "neo4j+s://"),
                                placeholder="neo4j+s://xxx.databases.neo4j.io")
    user = st.sidebar.text_input("User",
                                 value=secrets.get("user", "neo4j"))
    password = st.sidebar.text_input("Password", type="password",
                                     value=secrets.get("password", ""))
    return uri, user, password


def _sidebar_profile() -> Dict[str, List[float]]:
    """Agent profile configurator."""
    st.sidebar.header("🧠 Agent Profile")

    preset_name = st.sidebar.selectbox(
        "Preset", list(PRESETS.keys()), index=0,
        help="Selecting a preset resets the sliders below to its values.")
    if st.sidebar.button("⟲ Apply preset", use_container_width=True):
        st.session_state.agent_profile = copy.deepcopy(PRESETS[preset_name])
        st.rerun()

    profile = copy.deepcopy(st.session_state.agent_profile)

    width = st.sidebar.slider(
        "Tri half-width (a = peak - δ, c = peak + δ)",
        min_value=0.05, max_value=0.30, value=0.10, step=0.01,
        help="Used when the slider shifts the peak; "
             "the sliders only show the peak `b`.")

    with st.sidebar.expander("Emotions (20)", expanded=False):
        for em in ALL_EMOTIONS:
            key = f'emotion_{em}'
            current_peak = profile.get(key, [0.0, 0.0, 0.0])[1]
            new_peak = st.slider(em, 0.0, 1.0, float(current_peak), 0.01,
                                 key=f"sl_{key}")
            profile[key] = [max(0.0, new_peak - width), new_peak,
                            min(1.0, new_peak + width)]

    with st.sidebar.expander("Ethics (7)", expanded=True):
        for et in ALL_ETHICS:
            key = f'ethic_{et}'
            current_peak = profile.get(key, [0.0, 0.0, 0.0])[1]
            new_peak = st.slider(et, 0.0, 1.0, float(current_peak), 0.01,
                                 key=f"sl_{key}")
            profile[key] = [max(0.0, new_peak - width), new_peak,
                            min(1.0, new_peak + width)]

    st.session_state.agent_profile = profile
    return profile


# ──────────────────────────────────────────────────────────────────────
#  UI: Main
# ──────────────────────────────────────────────────────────────────────

def _render_state_tables(nav: AgentNavigator):
    """Current Tri-state of emotions and ethics."""
    col_em, col_eth = st.columns(2)
    with col_em:
        st.subheader("Emotions")
        df = pd.DataFrame(nav.emotional_model.as_table(),
                          columns=["name", "a", "b", "c", "peak"])
        st.dataframe(df, hide_index=True, use_container_width=True,
                     height=420)
    with col_eth:
        st.subheader("Ethics")
        df = pd.DataFrame(nav.ethical_model.as_table(),
                          columns=["name", "a", "b", "c", "peak"])
        st.dataframe(df, hide_index=True, use_container_width=True,
                     height=320)


def _render_step_panel(step: StepResult):
    """Details of the last step: candidates, breakdown, TSK rules."""
    st.subheader(f"Step: {step.from_node} → {step.to_node} "
                 f"(edge **{step.edge_id}**, ΣΔE = {step.total_dev})")

    cand_df = pd.DataFrame(
        [{'edge': c['edge_id'], 'to': c['next_id'],
          'ΣΔE': c['total_dev'], 'em': c['em_dev'], 'eth': c['eth_dev'],
          'chosen': c['edge_id'] == step.edge_id}
         for c in step.candidates]
    ).sort_values("ΣΔE")
    st.markdown("**Candidate edges**")
    st.dataframe(cand_df, hide_index=True, use_container_width=True)

    if step.deviation_details:
        with st.expander("ΣΔE breakdown by conditions of the selected edge"):
            det_df = pd.DataFrame(
                step.deviation_details,
                columns=["parameter", "req_peak", "agent_peak", "|Δ|"])
            st.dataframe(det_df, hide_index=True, use_container_width=True)

    col_em, col_eth = st.columns(2)
    with col_em:
        st.markdown("**Emotional TSK rules (active)**")
        if step.em_activations:
            df = pd.DataFrame(step.em_activations,
                              columns=["rule", "w", "description"])
            st.dataframe(df, hide_index=True, use_container_width=True)
        else:
            st.caption("— no activated rules")
        if step.em_deltas:
            st.markdown("**Δ emotions (TSK):** " +
                        ", ".join(f"`{k}`: {v:+.4f}"
                                  for k, v in step.em_deltas.items()))

    with col_eth:
        st.markdown("**Ethical TSK rules (active)**")
        if step.eth_activations:
            df = pd.DataFrame(step.eth_activations,
                              columns=["rule", "w", "description", "priority"])
            st.dataframe(df, hide_index=True, use_container_width=True)
        else:
            st.caption("— no activated rules")
        if step.eth_deltas:
            st.markdown("**Δ ethics (TSK):** " +
                        ", ".join(f"`{k}`: {v:+.4f}"
                                  for k, v in step.eth_deltas.items()))


# ──────────────────────────────────────────────────────────────────────
#  Main entry point
# ──────────────────────────────────────────────────────────────────────

def main():
    st.set_page_config(page_title="Scenario network · agent",
                       page_icon="🧭", layout="wide")
    _ss_init()

    st.title("🧭 Agent navigation through a scenario network")
    st.caption("TSK inference over the emotional and ethical models. "
               "The state graph is stored in Neo4j; at every step "
               "the edge with the minimal ΣΔE is selected.")

    # ── Sidebar ────────────────────────────────────────────────────
    uri, user, password = _sidebar_connection()
    profile = _sidebar_profile()

    st.sidebar.header("🎯 Controls")
    start_node = st.sidebar.text_input("Start node", value="V0")
    st.session_state.verbose_console = st.sidebar.checkbox(
        "Print verbose to console", value=False,
        help="Navigator logs will be printed to the Streamlit server's "
             "stderr/stdout.")

    col_a, col_b = st.sidebar.columns(2)
    connect_btn = col_a.button("🔌 Connect", use_container_width=True)
    reset_btn = col_b.button("⟲ Reset", use_container_width=True)

    if connect_btn:
        nav = _connect(uri, user, password)
        if nav is not None:
            # Close the old connection.
            old = st.session_state.nav
            if old is not None:
                try:
                    old.close()
                except Exception:  # noqa: BLE001
                    pass
            st.session_state.nav = nav
            try:
                st.session_state.topology = nav.fetch_graph_topology_full()
            except Exception as exc:  # noqa: BLE001
                st.session_state.topology = None
                st.warning(f"Failed to read graph topology: {exc}")
            nav.init_agent(profile)
            st.session_state.current_node = start_node
            st.session_state.finished = False
            st.session_state.history = []
            st.session_state.last_step = None
            st.rerun()

    if reset_btn and st.session_state.nav is not None:
        st.session_state.nav.init_agent(profile)
        st.session_state.current_node = start_node
        st.session_state.finished = False
        st.session_state.history = []
        st.session_state.last_step = None
        st.rerun()

    if st.session_state.connection_error:
        st.error(f"Connection error: {st.session_state.connection_error}")

    nav: Optional[AgentNavigator] = st.session_state.nav
    if nav is None:
        st.info("👈 Enter the Neo4j parameters in the sidebar and click "
                "\"Connect\".")
        return

    # ── Step and auto buttons ──────────────────────────────────────
    st.markdown("---")
    ctrl_step, ctrl_auto, ctrl_export = st.columns([1, 1, 2])
    do_step = ctrl_step.button("▶ Step", use_container_width=True,
                               disabled=st.session_state.finished)
    do_auto = ctrl_auto.button("⏭ Run to end", use_container_width=True,
                               disabled=st.session_state.finished)

    if do_step:
        s, err = _safe_step(nav)
        if err is not None:
            _show_neo4j_error(err)
        elif s is None:
            st.session_state.finished = True
            st.success(f"Node {st.session_state.current_node}: "
                       f"no outgoing edges. Run finished.")
        else:
            st.session_state.last_step = s
            st.session_state.history.append(_step_to_dict(s))
            st.session_state.current_node = s.to_node

    if do_auto:
        guard = 0
        while not st.session_state.finished and guard < 1000:
            guard += 1
            s, err = _safe_step(nav)
            if err is not None:
                _show_neo4j_error(err)
                break
            if s is None:
                st.session_state.finished = True
                break
            st.session_state.last_step = s
            st.session_state.history.append(_step_to_dict(s))
            st.session_state.current_node = s.to_node

    # ── History export ─────────────────────────────────────────────
    if st.session_state.history:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_payload = {
            'timestamp': ts,
            'profile': st.session_state.agent_profile,
            'start_node': start_node,
            'finished': st.session_state.finished,
            'path': [{'from': p[0], 'edge': p[1], 'to': p[2], 'total_dev': p[3]}
                     for p in nav.path],
            'history': st.session_state.history,
        }
        ctrl_export.download_button(
            "💾 Export run (JSON)",
            data=json.dumps(export_payload, ensure_ascii=False, indent=2),
            file_name=f"agent_run_{ts}.json",
            mime="application/json",
            use_container_width=True)

    # ── Current position ───────────────────────────────────────────
    st.markdown(f"### Current node: **`{st.session_state.current_node}`**")
    if st.session_state.finished:
        st.success("🏁 Run finished — no outgoing edges.")

    # ── Graph ──────────────────────────────────────────────────────
    if st.session_state.topology:
        nodes, edges = st.session_state.topology
        html = _render_graph(nodes, edges,
                             st.session_state.current_node,
                             nav.path)
        st.components.v1.html(html, height=540, scrolling=False)
    else:
        st.warning("Graph topology is not loaded — "
                   "click \"Connect\" again after connecting.")

    # ── Last-step panel ────────────────────────────────────────────
    if st.session_state.last_step is not None:
        st.markdown("---")
        _render_step_panel(st.session_state.last_step)

    # ── Agent state ────────────────────────────────────────────────
    st.markdown("---")
    st.header("Agent state")
    _render_state_tables(nav)

    # ── Path history ───────────────────────────────────────────────
    if nav.path:
        st.markdown("---")
        st.header("Traversed path")
        path_df = pd.DataFrame(
            [{'#': i + 1, 'from': p[0], 'edge': p[1], 'to': p[2],
              'ΣΔE': p[3]} for i, p in enumerate(nav.path)])
        st.dataframe(path_df, hide_index=True, use_container_width=True)
        path_str = " → ".join([nav.path[0][0]] + [s[2] for s in nav.path])
        st.markdown(f"**Short path:** `{path_str}`")


if __name__ == "__main__":
    main()
