# -*- coding: utf-8 -*-
"""Enterprise Design System CSS.
Sources: ui.shadcn.com (CSS tokens), carbondesignsystem.com (IBM Carbon patterns),
         ui.aceternity.com (3D cards / glass morphism).
"""
import streamlit as st

CSS = """<style>
/* ================================================================
   Enterprise Design System — shadcn/ui tokens + IBM Carbon patterns
   Sources: ui.shadcn.com, carbondesignsystem.com
   ================================================================ */

/* ----- CSS Custom Properties (Design Tokens) ----- */
:root {
  /* Surface */
  --bg-root: #09090b;
  --bg-surface: #12141a;
  --bg-card: #181b24;
  --bg-card-hover: #1e2230;
  --bg-glass: rgba(24, 27, 36, 0.82);
  --bg-input: #141720;

  /* Text */
  --text-primary: #f1f5f9;
  --text-secondary: #94a3b8;
  --text-muted: #64748b;
  --text-inverse: #09090b;

  /* Brand */
  --accent: #3b82f6;
  --accent-hover: #2563eb;
  --accent-muted: rgba(59, 130, 246, 0.12);

  /* Semantic */
  --green: #22c55e;
  --green-muted: rgba(34, 197, 94, 0.12);
  --amber: #f59e0b;
  --amber-muted: rgba(245, 158, 11, 0.12);
  --red: #ef4444;
  --red-muted: rgba(239, 68, 68, 0.12);
  --purple: #8b5cf6;
  --purple-muted: rgba(139, 92, 246, 0.12);

  /* Border */
  --border: #1e293b;
  --border-subtle: #1a2233;
  --border-accent: rgba(59, 130, 246, 0.3);

  /* Radii */
  --radius-sm: 6px;
  --radius: 8px;
  --radius-lg: 12px;
  --radius-xl: 16px;

  /* Shadows */
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.3);
  --shadow: 0 1px 3px rgba(0,0,0,0.4), 0 1px 2px rgba(0,0,0,0.2);
  --shadow-lg: 0 4px 16px rgba(0,0,0,0.5);
  --shadow-glow: 0 0 20px rgba(59, 130, 246, 0.15);

  /* Typography */
  --font-mono: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
  --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;

  /* Spacing */
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-8: 32px;
  --space-10: 40px;
}

/* ===== BASE OVERRIDES ===== */
html, body, .stApp, [data-testid="stApp"] {
  background: var(--bg-root);
  color: var(--text-primary);
  font-family: var(--font-sans);
}
[data-testid="stAppViewContainer"],
[data-testid="stAppViewBlockContainer"],
.main, .block-container {
  background: var(--bg-root);
}
[data-testid="stHeader"] { background: transparent; }
[data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stAppDeployButton"], #MainMenu { display: none !important; }

/* ===== TOP NAV (floating glass) ===== */
.top-nav {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 28px;
  background: var(--bg-glass);
  backdrop-filter: blur(16px) saturate(120%);
  -webkit-backdrop-filter: blur(16px) saturate(120%);
  border-bottom: 1px solid var(--border-subtle);
  position: sticky; top: 0; z-index: 999;
  margin-bottom: var(--space-6);
}
.brand {
  font-weight: 700; font-size: 1.05em;
  letter-spacing: -0.01em;
  background: linear-gradient(135deg, var(--accent), var(--purple));
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  background-clip: text;
}
.nav-links { display: flex; gap: 4px; flex-wrap: wrap; }
.nav-link {
  padding: 6px 14px; border-radius: var(--radius-sm);
  color: var(--text-secondary); text-decoration: none;
  font-size: 0.85em; font-weight: 500;
  transition: all 0.15s ease;
  letter-spacing: 0.01em;
}
.nav-link:hover {
  background: var(--accent-muted);
  color: var(--accent);
}

/* ===== SIDEBAR (sleek dark) ===== */
[data-testid="stSidebar"] {
  background: var(--bg-surface);
  border-right: 1px solid var(--border);
}
[data-testid="stSidebarNav"] a {
  padding: 8px 14px; border-radius: var(--radius-sm);
  color: var(--text-secondary); font-size: 0.9em;
  transition: all 0.12s ease;
}
[data-testid="stSidebarNav"] a:hover {
  background: var(--accent-muted); color: var(--accent);
}
[data-testid="stSidebarNav"] a[aria-current="page"] {
  background: var(--accent-muted); color: var(--accent);
  font-weight: 600; border-left: 2px solid var(--accent);
}

/* ===== BUTTONS ===== */
.stButton button {
  border-radius: var(--radius); font-weight: 500;
  transition: all 0.15s ease;
  background: var(--bg-card); border: 1px solid var(--border);
  color: var(--text-primary); font-size: 0.9em;
  padding: 8px 16px;
}
.stButton button:hover {
  border-color: var(--accent);
  background: var(--accent-muted);
  transform: translateY(-1px);
}
.stButton button:active { transform: translateY(0); }
.stButton button[kind="primary"] {
  background: var(--accent); color: #fff;
  border-color: var(--accent); font-weight: 600;
}
.stButton button[kind="primary"]:hover {
  background: var(--accent-hover);
  box-shadow: var(--shadow-glow);
}

/* ===== METRIC CARDS (glass morphism) ===== */
[data-testid="stMetric"] {
  background: var(--bg-glass);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  padding: 18px 22px;
  transition: all 0.2s ease;
}
[data-testid="stMetric"]:hover {
  border-color: var(--border-accent);
  box-shadow: var(--shadow-glow);
  transform: translateY(-2px);
}
[data-testid="stMetric"] label {
  color: var(--text-muted);
  font-size: 0.75em; font-weight: 600;
  letter-spacing: 0.05em; text-transform: uppercase;
}
[data-testid="stMetric"] p {
  color: var(--text-primary);
  font-size: 1.6em; font-weight: 800;
  letter-spacing: -0.02em;
}

/* ===== INPUTS ===== */
.stTextInput input, .stTextArea textarea,
[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
  background: var(--bg-input); border: 1px solid var(--border);
  border-radius: var(--radius); color: var(--text-primary);
  font-size: 0.92em; transition: all 0.15s ease;
}
.stTextInput input:focus, .stTextArea textarea:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-muted);
}

/* ===== EXPANDER ===== */
.streamlit-expanderHeader {
  background: var(--bg-card); border-radius: var(--radius);
  color: var(--text-primary); font-weight: 500;
  border: 1px solid var(--border-subtle);
}
.streamlit-expanderContent {
  background: var(--bg-card); border: 1px solid var(--border-subtle);
  border-radius: 0 0 var(--radius) var(--radius);
  border-top: none;
}

/* ===== 3D DATA CARD (Aceternity) ===== */
.data-card-3d {
  background: var(--bg-glass);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  padding: 20px 16px;
  transform: perspective(800px) rotateX(2deg);
  transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
}
.data-card-3d:hover {
  transform: perspective(800px) rotateX(0deg) translateY(-4px);
  border-color: var(--border-accent);
  box-shadow: var(--shadow-glow);
}

/* ===== STATUS BADGES ===== */
.badge { display: inline-block; padding: 2px 10px; border-radius: 100px;
         font-size: 0.78em; font-weight: 600; letter-spacing: 0.02em; }
.badge-green { background: var(--green-muted); color: var(--green); }
.badge-amber { background: var(--amber-muted); color: var(--amber); }
.badge-red { background: var(--red-muted); color: var(--red); }
.badge-purple { background: var(--purple-muted); color: var(--purple); }
.badge-blue { background: var(--accent-muted); color: var(--accent); }

/* ===== CONTAINERS ===== */
div[data-testid="stForm"] {
  background: var(--bg-card); border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg); padding: var(--space-5);
}
div[data-testid="stVerticalBlock"] > div {
  background: transparent;
}

/* ===== DIVIDERS ===== */
hr { border-color: var(--border); margin: var(--space-4) 0; }

/* ===== SCROLLBAR ===== */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--bg-surface); }
::-webkit-scrollbar-thumb {
  background: var(--border); border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover { background: #334155; }

/* ===== NOTIFICATIONS ===== */
div[data-testid="stNotification"] {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: var(--radius);
}

/* ===== IFRAME/POPOVER ===== */
iframe { background: var(--bg-root); }
[data-testid="stPopover"] { background: var(--bg-card); }

/* ===== PROGRESS BAR ===== */
[data-testid="stProgress"] > div > div {
  background: linear-gradient(90deg, var(--accent), var(--purple));
  border-radius: 100px;
}

/* ===== TABS ===== */
.stTabs [data-baseweb="tab-list"] {
  gap: 2px; background: var(--bg-surface);
  border-radius: var(--radius); padding: 4px;
  border: 1px solid var(--border-subtle);
}
.stTabs [data-baseweb="tab"] {
  border-radius: var(--radius-sm); padding: 6px 16px;
  color: var(--text-secondary); font-weight: 500;
  transition: all 0.12s ease;
}
.stTabs [aria-selected="true"] {
  background: var(--bg-card); color: var(--text-primary);
}

/* ===== DATA TABLE OVERRIDES (Streamlit native) ===== */
[data-testid="stTable"] {
  background: var(--bg-card); border-radius: var(--radius-lg);
  border: 1px solid var(--border-subtle); overflow: hidden;
}
[data-testid="stTable"] th {
  background: var(--bg-surface); color: var(--text-muted);
  font-weight: 600; font-size: 0.78em; letter-spacing: 0.04em;
  text-transform: uppercase; padding: 10px 14px;
}
[data-testid="stTable"] td {
  color: var(--text-primary); padding: 8px 14px;
  border-bottom: 1px solid var(--border-subtle);
}

/* ===== CODE BLOCKS ===== */
code, pre {
  background: var(--bg-input); border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm); font-family: var(--font-mono);
  font-size: 0.85em;
}

/* ===== EMPTY/INFO STATES ===== */
[data-testid="stInfo"] {
  background: var(--accent-muted); border: 1px solid var(--border-accent);
  border-radius: var(--radius); color: var(--accent);
}
[data-testid="stWarning"] {
  background: var(--amber-muted); border: 1px solid rgba(245,158,11,0.2);
  border-radius: var(--radius); color: var(--amber);
}
[data-testid="stError"] {
  background: var(--red-muted); border: 1px solid rgba(239,68,68,0.2);
  border-radius: var(--radius); color: var(--red);
}
[data-testid="stSuccess"] {
  background: var(--green-muted); border: 1px solid rgba(34,197,94,0.2);
  border-radius: var(--radius); color: var(--green);
}

/* ===== ANIMATIONS ===== */
@keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
@keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.5; } }
.animate-fade-in { animation: fadeIn 0.4s ease-out; }

/* ===== DARK MODE FORCE (selective, non-brute-force) ===== */
[data-testid="stApp"] { background: var(--bg-root); }
[data-testid="stSidebar"] { background: var(--bg-surface); }

</style>"""

def inject_theme():
    st.markdown(CSS, unsafe_allow_html=True)

SIDEBAR_CSS = CSS
