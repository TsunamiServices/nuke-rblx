import discord
from discord import app_commands
import json, random, string, threading, os, logging
from datetime import datetime, timedelta

# =========================
# LOGGING
# =========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

# =========================
# ENV
# =========================
BOT_TOKEN    = os.environ.get("BOT_TOKEN")
ADMIN_ROLE_ID = int(os.environ.get("ADMIN_ROLE_ID", 0))
GUILD_ID      = os.environ.get("GUILD_ID")          # ← ADICIONE no Railway para sync instantâneo

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN não encontrado nas variáveis de ambiente!")

# =========================
# DATABASE (JSON)
# Nota: no Railway o filesystem é efêmero.
# Para persistência real, use Railway + PostgreSQL ou Redis.
# =========================
DB_FILE = "/tmp/keys.json"   # /tmp sobrevive ao processo mas não ao redeploy

def load_keys() -> dict:
    try:
        with open(DB_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_keys(keys: dict):
    with open(DB_FILE, "w") as f:
        json.dump(keys, f, indent=4)

def generate_key() -> str:
    def part():
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"WHITE-{part()}-{part()}-{part()}"

def clean_expired() -> dict:
    keys = load_keys()
    now  = datetime.utcnow()
    valid = {k: v for k, v in keys.items()
             if datetime.fromisoformat(v["expires"]) > now}
    save_keys(valid)
    return valid

def parse_duration(d: str) -> timedelta | None:
    d = d.lower().strip()
    try:
        if d.endswith("d"):  return timedelta(days=int(d[:-1]))
        if d.endswith("m"):  return timedelta(days=int(d[:-1]) * 30)
        if d.endswith("a"):  return timedelta(days=int(d[:-1]) * 365)
        if d.endswith("h"):  return timedelta(hours=int(d[:-1]))
    except ValueError:
        pass
    return None

# =========================
# FLASK DASHBOARD
# =========================
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "white2024")

PUBLIC_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>White External</title>
<link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Rajdhani:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#080b0f;--surface:#0d1117;--border:#1a2332;--border-glow:#e63946;
  --red:#e63946;--red-dim:#7f1d1d;--green:#22c55e;--green-dim:#14532d;
  --text:#c9d1d9;--text-dim:#8b949e;--mono:'Share Tech Mono',monospace;
  --sans:'Rajdhani',sans-serif;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:var(--sans);min-height:100vh;
  overflow-x:hidden}

/* scanline overlay */
body::before{content:'';position:fixed;inset:0;pointer-events:none;z-index:999;
  background:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,0,0,.08) 2px,rgba(0,0,0,.08) 4px)}

.wrap{max-width:960px;margin:0 auto;padding:2.5rem 1.5rem}

/* ── HEADER ── */
header{display:flex;align-items:center;justify-content:space-between;
  padding-bottom:2rem;border-bottom:1px solid var(--border);margin-bottom:2.5rem}
.logo{display:flex;align-items:center;gap:.75rem}
.logo-icon{width:38px;height:38px;border:2px solid var(--red);border-radius:6px;
  display:grid;place-items:center;font-size:1.1rem;color:var(--red);
  box-shadow:0 0 12px #e6394430;animation:pulse 3s ease-in-out infinite}
@keyframes pulse{0%,100%{box-shadow:0 0 12px #e6394430}50%{box-shadow:0 0 22px #e6394460}}
.logo-text{font-size:1.5rem;font-weight:700;letter-spacing:.06em;color:#f1f5f9}
.logo-text span{color:var(--red)}
.version{font-family:var(--mono);font-size:.7rem;color:var(--text-dim);
  background:#0d1117;border:1px solid var(--border);padding:3px 10px;border-radius:4px}
.admin-btn{font-family:var(--sans);font-size:.85rem;font-weight:600;
  color:var(--text-dim);background:transparent;border:1px solid var(--border);
  padding:6px 16px;border-radius:6px;cursor:pointer;text-decoration:none;
  transition:all .2s;letter-spacing:.04em}
.admin-btn:hover{color:var(--red);border-color:var(--red);background:#e6394410}

/* ── STATS ── */
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:1rem;margin-bottom:2.5rem}
.stat{background:var(--surface);border:1px solid var(--border);border-radius:10px;
  padding:1.25rem 1.5rem;position:relative;overflow:hidden;transition:border-color .2s}
.stat:hover{border-color:#1e3a5f}
.stat::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;
  background:linear-gradient(90deg,transparent,var(--red),transparent);opacity:.6}
.stat-num{font-family:var(--mono);font-size:2.2rem;font-weight:400;
  color:var(--red);line-height:1;margin-bottom:.35rem}
.stat-lbl{font-size:.75rem;font-weight:600;text-transform:uppercase;
  letter-spacing:.1em;color:var(--text-dim)}

/* ── TABLE ── */
.table-wrap{background:var(--surface);border:1px solid var(--border);border-radius:12px;overflow:hidden}
.table-header{display:flex;align-items:center;justify-content:space-between;
  padding:1rem 1.5rem;border-bottom:1px solid var(--border)}
.table-title{font-size:1rem;font-weight:700;letter-spacing:.05em;
  text-transform:uppercase;color:var(--text-dim)}
.dot{width:8px;height:8px;border-radius:50%;background:var(--green);
  box-shadow:0 0 8px var(--green);display:inline-block;margin-right:.5rem;
  animation:blink 2s ease-in-out infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.3}}
table{width:100%;border-collapse:collapse}
th{padding:.75rem 1.5rem;text-align:left;font-size:.72rem;font-weight:700;
  text-transform:uppercase;letter-spacing:.09em;color:var(--text-dim);
  background:#0a0e14;border-bottom:1px solid var(--border)}
tbody tr{border-bottom:1px solid #0d1117;transition:background .15s}
tbody tr:hover{background:#0d1520}
td{padding:.85rem 1.5rem;font-size:.9rem;vertical-align:middle}
.key-mono{font-family:var(--mono);font-size:.82rem;color:#7dd3fc;letter-spacing:.03em}
.date-col{font-family:var(--mono);font-size:.8rem;color:var(--text-dim)}
.badge{display:inline-flex;align-items:center;gap:5px;padding:3px 11px;
  border-radius:20px;font-size:.72rem;font-weight:700;letter-spacing:.04em;text-transform:uppercase}
.badge-active{background:#052e16;color:var(--green);border:1px solid #166534}
.badge-used{background:#1c1207;color:#f59e0b;border:1px solid #92400e}
.empty-state{text-align:center;padding:4rem 2rem;color:var(--text-dim)}
.empty-state .e-icon{font-size:2.5rem;margin-bottom:1rem;opacity:.3}
footer{text-align:center;margin-top:2.5rem;color:var(--text-dim);
  font-family:var(--mono);font-size:.72rem;opacity:.5}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="logo">
      <div class="logo-icon">W</div>
      <div>
        <div class="logo-text">White<span>External</span></div>
      </div>
    </div>
    <div style="display:flex;align-items:center;gap:1rem">
      <span class="version">v1.0</span>
      <a href="/admin" class="admin-btn">Admin →</a>
    </div>
  </header>

  <div class="stats">
    <div class="stat">
      <div class="stat-num">{{ total }}</div>
      <div class="stat-lbl">Keys Ativas</div>
    </div>
    <div class="stat">
      <div class="stat-num">{{ used_count }}</div>
      <div class="stat-lbl">Já Utilizadas</div>
    </div>
    <div class="stat">
      <div class="stat-num">{{ available }}</div>
      <div class="stat-lbl">Disponíveis</div>
    </div>
  </div>

  <div class="table-wrap">
    <div class="table-header">
      <span class="table-title"><span class="dot"></span>Keys em circulação</span>
    </div>
    {% if keys %}
    <table>
      <thead><tr>
        <th>Key</th><th>Criada em</th><th>Expira em</th><th>Status</th>
      </tr></thead>
      <tbody>
      {% for k,v in keys.items() %}
      <tr>
        <td class="key-mono">{{ k }}</td>
        <td class="date-col">{{ v.get('created_at','—')[:10] }}</td>
        <td class="date-col">{{ v['expires'][:10] }}</td>
        <td>
          {% if v.get('used') %}
            <span class="badge badge-used">⬡ Utilizada</span>
          {% else %}
            <span class="badge badge-active">● Ativa</span>
          {% endif %}
        </td>
      </tr>
      {% endfor %}
      </tbody>
    </table>
    {% else %}
    <div class="empty-state">
      <div class="e-icon">⬡</div>
      <div>Nenhuma key ativa no momento.</div>
    </div>
    {% endif %}
  </div>
  <footer>WHITE EXTERNAL SYSTEMS // ACESSO RESTRITO</footer>
</div>
</body>
</html>"""

LOGIN_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Admin — White External</title>
<link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Rajdhani:wght@500;600;700&display=swap" rel="stylesheet">
<style>
:root{--bg:#080b0f;--surface:#0d1117;--border:#1a2332;--red:#e63946;
  --text:#c9d1d9;--text-dim:#8b949e;--mono:'Share Tech Mono',monospace;--sans:'Rajdhani',sans-serif}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:var(--sans);
  min-height:100vh;display:grid;place-items:center}
body::before{content:'';position:fixed;inset:0;pointer-events:none;
  background:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,0,0,.07) 2px,rgba(0,0,0,.07) 4px)}
.box{background:var(--surface);border:1px solid var(--border);border-radius:14px;
  padding:2.5rem;width:100%;max-width:380px;position:relative;overflow:hidden}
.box::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;
  background:linear-gradient(90deg,transparent,var(--red),transparent)}
.icon{width:48px;height:48px;border:2px solid var(--red);border-radius:8px;
  display:grid;place-items:center;font-size:1.4rem;color:var(--red);
  margin:0 auto 1.5rem;box-shadow:0 0 20px #e6394430}
h2{text-align:center;font-size:1.3rem;font-weight:700;letter-spacing:.06em;
  margin-bottom:.4rem}
.sub{text-align:center;font-family:var(--mono);font-size:.72rem;
  color:var(--text-dim);margin-bottom:2rem}
label{display:block;font-size:.75rem;font-weight:700;text-transform:uppercase;
  letter-spacing:.08em;color:var(--text-dim);margin-bottom:.5rem}
input{width:100%;background:#080b0f;border:1px solid var(--border);border-radius:7px;
  padding:.75rem 1rem;font-family:var(--mono);font-size:.9rem;color:var(--text);
  outline:none;transition:border-color .2s}
input:focus{border-color:var(--red)}
.btn{width:100%;margin-top:1.5rem;padding:.8rem;background:var(--red);
  border:none;border-radius:7px;color:#fff;font-family:var(--sans);
  font-size:1rem;font-weight:700;letter-spacing:.06em;cursor:pointer;
  transition:opacity .2s}
.btn:hover{opacity:.85}
.err{background:#7f1d1d30;border:1px solid #991b1b;border-radius:7px;
  padding:.65rem 1rem;margin-bottom:1rem;font-size:.85rem;color:#fca5a5;text-align:center}
.back{display:block;text-align:center;margin-top:1.2rem;font-family:var(--mono);
  font-size:.72rem;color:var(--text-dim);text-decoration:none}
.back:hover{color:var(--red)}
</style>
</head>
<body>
<div class="box">
  <div class="icon">⬡</div>
  <h2>PAINEL ADMIN</h2>
  <p class="sub">White External // Acesso Restrito</p>
  {% if error %}<div class="err">{{ error }}</div>{% endif %}
  <form method="POST" action="/admin/login">
    <label>Senha de Acesso</label>
    <input type="password" name="password" placeholder="••••••••" autofocus>
    <button class="btn" type="submit">ENTRAR</button>
  </form>
  <a class="back" href="/">← Voltar ao site</a>
</div>
</body>
</html>"""

ADMIN_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Admin — White External</title>
<link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Rajdhani:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#080b0f;--surface:#0d1117;--surface2:#111827;--border:#1a2332;
  --red:#e63946;--green:#22c55e;--yellow:#f59e0b;--blue:#38bdf8;
  --text:#c9d1d9;--text-dim:#8b949e;
  --mono:'Share Tech Mono',monospace;--sans:'Rajdhani',sans-serif
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:var(--sans);min-height:100vh;overflow-x:hidden}
body::before{content:'';position:fixed;inset:0;pointer-events:none;z-index:999;
  background:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,0,0,.06) 2px,rgba(0,0,0,.06) 4px)}
.wrap{max-width:1100px;margin:0 auto;padding:2rem 1.5rem}

/* HEADER */
header{display:flex;align-items:center;justify-content:space-between;
  padding-bottom:1.75rem;border-bottom:1px solid var(--border);margin-bottom:2rem}
.logo{display:flex;align-items:center;gap:.75rem}
.logo-icon{width:36px;height:36px;border:2px solid var(--red);border-radius:6px;
  display:grid;place-items:center;font-size:1rem;color:var(--red);
  box-shadow:0 0 14px #e6394440;animation:glow 3s ease-in-out infinite}
@keyframes glow{0%,100%{box-shadow:0 0 14px #e6394440}50%{box-shadow:0 0 24px #e6394470}}
.logo-name{font-size:1.3rem;font-weight:700;letter-spacing:.05em}
.logo-name span{color:var(--red)}
.hdr-right{display:flex;align-items:center;gap:.75rem}
.chip{font-family:var(--mono);font-size:.7rem;color:var(--text-dim);
  background:var(--surface2);border:1px solid var(--border);padding:4px 12px;border-radius:20px}
.logout{font-family:var(--sans);font-size:.82rem;font-weight:600;color:var(--red);
  background:transparent;border:1px solid #991b1b;padding:5px 14px;border-radius:6px;
  cursor:pointer;text-decoration:none;transition:all .2s;letter-spacing:.04em}
.logout:hover{background:#e6394420}

/* STATS */
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:1rem;margin-bottom:2rem}
.stat{background:var(--surface);border:1px solid var(--border);border-radius:10px;
  padding:1.2rem 1.4rem;position:relative;overflow:hidden;transition:transform .15s,border-color .2s}
.stat:hover{transform:translateY(-1px);border-color:#1e3a5f}
.stat-bar{position:absolute;top:0;left:0;right:0;height:2px}
.red-bar{background:linear-gradient(90deg,transparent,var(--red),transparent)}
.green-bar{background:linear-gradient(90deg,transparent,var(--green),transparent)}
.yellow-bar{background:linear-gradient(90deg,transparent,var(--yellow),transparent)}
.blue-bar{background:linear-gradient(90deg,transparent,var(--blue),transparent)}
.stat-num{font-family:var(--mono);font-size:2rem;line-height:1;margin-bottom:.3rem}
.c-red{color:var(--red)}.c-green{color:var(--green)}.c-yellow{color:var(--yellow)}.c-blue{color:var(--blue)}
.stat-lbl{font-size:.73rem;font-weight:700;text-transform:uppercase;letter-spacing:.09em;color:var(--text-dim)}

/* TOOLBAR */
.toolbar{display:flex;align-items:center;justify-content:space-between;
  flex-wrap:wrap;gap:.75rem;margin-bottom:1rem}
.toolbar-left{display:flex;align-items:center;gap:.75rem}
.section-title{font-size:1rem;font-weight:700;text-transform:uppercase;
  letter-spacing:.07em;color:var(--text-dim)}
.dot{width:8px;height:8px;border-radius:50%;background:var(--green);
  box-shadow:0 0 6px var(--green);display:inline-block;margin-right:.4rem;
  animation:blink 2s ease-in-out infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.25}}
.search{background:var(--surface2);border:1px solid var(--border);border-radius:7px;
  padding:.5rem .9rem;font-family:var(--mono);font-size:.8rem;color:var(--text);
  outline:none;width:220px;transition:border-color .2s}
.search:focus{border-color:var(--red)}
.filter-btn{font-family:var(--sans);font-size:.8rem;font-weight:600;padding:5px 14px;
  border-radius:6px;cursor:pointer;border:1px solid var(--border);
  background:transparent;color:var(--text-dim);transition:all .2s;letter-spacing:.04em}
.filter-btn.active,.filter-btn:hover{border-color:var(--red);color:var(--red);background:#e6394415}

/* TABLE */
.tbl-wrap{background:var(--surface);border:1px solid var(--border);border-radius:12px;overflow:hidden}
table{width:100%;border-collapse:collapse}
th{padding:.7rem 1.2rem;text-align:left;font-size:.71rem;font-weight:700;
  text-transform:uppercase;letter-spacing:.09em;color:var(--text-dim);
  background:#0a0e14;border-bottom:1px solid var(--border);white-space:nowrap}
tbody tr{border-bottom:1px solid #0b0f15;transition:background .12s;cursor:default}
tbody tr:hover{background:#0d1520}
tbody tr.row-used{opacity:.65}
td{padding:.9rem 1.2rem;font-size:.88rem;vertical-align:middle}
.key-mono{font-family:var(--mono);font-size:.8rem;color:var(--blue)}
.date-mono{font-family:var(--mono);font-size:.78rem;color:var(--text-dim)}
.creator{font-size:.82rem;color:var(--text-dim)}

/* BADGES */
.badge{display:inline-flex;align-items:center;gap:4px;padding:3px 10px;
  border-radius:20px;font-size:.7rem;font-weight:700;letter-spacing:.04em;text-transform:uppercase;white-space:nowrap}
.b-active{background:#052e16;color:var(--green);border:1px solid #166534}
.b-used{background:#1c1207;color:var(--yellow);border:1px solid #92400e}

/* ACTIONS */
.actions{display:flex;align-items:center;gap:.5rem}
.btn-icon{display:inline-flex;align-items:center;justify-content:center;
  width:30px;height:30px;border-radius:6px;border:1px solid var(--border);
  background:transparent;cursor:pointer;font-size:.9rem;transition:all .15s;
  position:relative}
.btn-icon:hover{border-color:var(--red);background:#e6394415}
.btn-icon.copy:hover{border-color:var(--blue);background:#38bdf815}
.btn-icon.mark-used:hover{border-color:var(--yellow);background:#f59e0b15}
.btn-icon.del:hover{border-color:var(--red);background:#e6394420}
.tooltip{position:absolute;bottom:calc(100% + 6px);left:50%;transform:translateX(-50%);
  background:#1e2d3d;border:1px solid #2a3f55;border-radius:5px;padding:3px 8px;
  font-family:var(--mono);font-size:.65rem;color:var(--text);white-space:nowrap;
  pointer-events:none;opacity:0;transition:opacity .15s}
.btn-icon:hover .tooltip{opacity:1}

/* COPY FEEDBACK */
.copied{position:fixed;bottom:1.5rem;right:1.5rem;background:#052e16;
  border:1px solid #166534;color:var(--green);padding:.65rem 1.2rem;
  border-radius:8px;font-family:var(--mono);font-size:.8rem;z-index:1000;
  transform:translateY(10px);opacity:0;transition:all .25s;pointer-events:none}
.copied.show{transform:translateY(0);opacity:1}

/* MODAL */
.overlay{position:fixed;inset:0;background:#000a;z-index:100;
  display:none;place-items:center}
.overlay.open{display:grid}
.modal{background:var(--surface);border:1px solid #991b1b;border-radius:12px;
  padding:2rem;width:100%;max-width:400px;position:relative}
.modal-title{font-size:1.1rem;font-weight:700;color:#fca5a5;margin-bottom:.6rem}
.modal-sub{font-size:.85rem;color:var(--text-dim);margin-bottom:1.5rem;line-height:1.5}
.modal-key{font-family:var(--mono);font-size:.78rem;color:var(--blue);
  background:#080b0f;padding:.5rem .85rem;border-radius:6px;margin-bottom:1.5rem;
  border:1px solid var(--border);word-break:break-all}
.modal-actions{display:flex;gap:.75rem;justify-content:flex-end}
.btn-cancel{font-family:var(--sans);font-size:.88rem;font-weight:600;
  padding:.55rem 1.2rem;border-radius:7px;border:1px solid var(--border);
  background:transparent;color:var(--text-dim);cursor:pointer;letter-spacing:.04em}
.btn-cancel:hover{border-color:#334155;color:var(--text)}
.btn-confirm{font-family:var(--sans);font-size:.88rem;font-weight:700;
  padding:.55rem 1.2rem;border-radius:7px;border:none;
  background:var(--red);color:#fff;cursor:pointer;letter-spacing:.04em;transition:opacity .2s}
.btn-confirm:hover{opacity:.85}

.empty-state{text-align:center;padding:4rem 2rem;color:var(--text-dim)}
footer{text-align:center;margin-top:2rem;font-family:var(--mono);font-size:.68rem;color:var(--text-dim);opacity:.4}
</style>
</head>
<body>
<div class="wrap">

  <header>
    <div class="logo">
      <div class="logo-icon">W</div>
      <div class="logo-name">White<span>External</span> <span style="font-size:.75rem;color:var(--text-dim);font-weight:500">// Admin</span></div>
    </div>
    <div class="hdr-right">
      <span class="chip" id="clock">--:--:--</span>
      <a href="/" class="chip" style="text-decoration:none;cursor:pointer">← Site</a>
      <a href="/admin/logout" class="logout">Sair</a>
    </div>
  </header>

  <!-- STATS -->
  <div class="stats">
    <div class="stat"><div class="stat-bar red-bar"></div>
      <div class="stat-num c-red">{{ total }}</div><div class="stat-lbl">Total de Keys</div></div>
    <div class="stat"><div class="stat-bar green-bar"></div>
      <div class="stat-num c-green">{{ available }}</div><div class="stat-lbl">Disponíveis</div></div>
    <div class="stat"><div class="stat-bar yellow-bar"></div>
      <div class="stat-num c-yellow">{{ used_count }}</div><div class="stat-lbl">Utilizadas</div></div>
    <div class="stat"><div class="stat-bar blue-bar"></div>
      <div class="stat-num c-blue">{{ expiring_soon }}</div><div class="stat-lbl">Exp. em 3 dias</div></div>
  </div>

  <!-- TOOLBAR -->
  <div class="toolbar">
    <div class="toolbar-left">
      <span class="section-title"><span class="dot"></span>Gerenciar Keys</span>
      <button class="filter-btn active" onclick="filter(this,'all')">Todas</button>
      <button class="filter-btn" onclick="filter(this,'active')">Ativas</button>
      <button class="filter-btn" onclick="filter(this,'used')">Utilizadas</button>
    </div>
    <input class="search" type="text" placeholder="Buscar key..." oninput="search(this.value)">
  </div>

  <!-- TABLE -->
  <div class="tbl-wrap">
    {% if keys %}
    <table id="keytable">
      <thead><tr>
        <th>#</th><th>Key</th><th>Criado por</th><th>Criada em</th><th>Expira em</th><th>Status</th><th>Ações</th>
      </tr></thead>
      <tbody>
      {% for k, v in keys.items() %}
      <tr class="key-row {% if v.get('used') %}row-used{% endif %}" data-key="{{ k }}" data-used="{{ 'true' if v.get('used') else 'false' }}">
        <td class="date-mono">{{ loop.index }}</td>
        <td class="key-mono">{{ k }}</td>
        <td class="creator">{{ v.get('created_by', '—') }}</td>
        <td class="date-mono">{{ v.get('created_at','—')[:10] }}</td>
        <td class="date-mono">{{ v['expires'][:10] }}</td>
        <td id="badge-{{ loop.index }}">
          {% if v.get('used') %}
            <span class="badge b-used">⬡ Utilizada</span>
          {% else %}
            <span class="badge b-active">● Ativa</span>
          {% endif %}
        </td>
        <td>
          <div class="actions">
            <button class="btn-icon copy" onclick="copyKey('{{ k }}')">
              📋<span class="tooltip">Copiar Key</span>
            </button>
            <button class="btn-icon mark-used" onclick="toggleUsed('{{ k }}', this, '{{ loop.index }}', {{ 'true' if v.get('used') else 'false' }})">
              {{ '↩' if v.get('used') else '✓' }}<span class="tooltip">{{ 'Desmarcar' if v.get('used') else 'Marcar como Usada' }}</span>
            </button>
            <button class="btn-icon del" onclick="confirmDelete('{{ k }}')">
              🗑<span class="tooltip">Deletar</span>
            </button>
          </div>
        </td>
      </tr>
      {% endfor %}
      </tbody>
    </table>
    {% else %}
    <div class="empty-state">
      <div style="font-size:2rem;opacity:.2;margin-bottom:1rem">⬡</div>
      Nenhuma key cadastrada.
    </div>
    {% endif %}
  </div>

  <footer>WHITE EXTERNAL ADMIN PANEL // {{ total }} KEYS REGISTRADAS</footer>
</div>

<!-- COPY TOAST -->
<div class="copied" id="toast">✓ Key copiada!</div>

<!-- DELETE MODAL -->
<div class="overlay" id="del-modal">
  <div class="modal">
    <div class="modal-title">⚠ Confirmar exclusão</div>
    <div class="modal-sub">Você está prestes a remover permanentemente a seguinte key:</div>
    <div class="modal-key" id="del-key-display"></div>
    <div class="modal-actions">
      <button class="btn-cancel" onclick="closeModal()">Cancelar</button>
      <button class="btn-confirm" onclick="deleteKey()">Deletar</button>
    </div>
  </div>
</div>

<script>
let pendingDeleteKey = null;

// Clock
function tick(){
  const n=new Date();
  document.getElementById('clock').textContent=n.toLocaleTimeString('pt-BR');
}
setInterval(tick,1000); tick();

// Copy
function copyKey(k){
  navigator.clipboard.writeText(k);
  const t=document.getElementById('toast');
  t.classList.add('show');
  setTimeout(()=>t.classList.remove('show'),2000);
}

// Filter
let currentFilter='all';
function filter(btn,type){
  currentFilter=type;
  document.querySelectorAll('.filter-btn').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  applyFilters();
}
function search(q){applyFilters(q);}
function applyFilters(q=''){
  const val=q.toLowerCase();
  document.querySelectorAll('.key-row').forEach(row=>{
    const key=row.dataset.key.toLowerCase();
    const used=row.dataset.used==='true';
    const matchSearch=key.includes(val);
    const matchFilter=currentFilter==='all'||(currentFilter==='active'&&!used)||(currentFilter==='used'&&used);
    row.style.display=(matchSearch&&matchFilter)?'':'none';
  });
}

// Toggle used
function toggleUsed(key, btn, idx, isUsed){
  fetch('/admin/api/toggle-used',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({key})
  }).then(r=>r.json()).then(d=>{
    if(d.ok){
      const newUsed=d.used;
      const row=document.querySelector('[data-key="'+key+'"]');
      row.dataset.used=newUsed?'true':'false';
      row.classList.toggle('row-used',newUsed);
      document.getElementById('badge-'+idx).innerHTML=newUsed
        ?'<span class="badge b-used">⬡ Utilizada</span>'
        :'<span class="badge b-active">● Ativa</span>';
      btn.textContent=newUsed?'↩':'✓';
      btn.querySelector('.tooltip').textContent=newUsed?'Desmarcar':'Marcar como Usada';
    }
  });
}

// Delete modal
function confirmDelete(key){
  pendingDeleteKey=key;
  document.getElementById('del-key-display').textContent=key;
  document.getElementById('del-modal').classList.add('open');
}
function closeModal(){
  document.getElementById('del-modal').classList.remove('open');
  pendingDeleteKey=null;
}
function deleteKey(){
  if(!pendingDeleteKey)return;
  fetch('/admin/api/delete-key',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({key:pendingDeleteKey})
  }).then(r=>r.json()).then(d=>{
    if(d.ok){
      document.querySelector('[data-key="'+pendingDeleteKey+'"]').remove();
    }
    closeModal();
  });
}
// Close modal on overlay click
document.getElementById('del-modal').addEventListener('click',function(e){
  if(e.target===this)closeModal();
});
</script>
</body>
</html>"""

from flask import Flask, render_template_string, request, redirect, session, jsonify
from functools import wraps

flask_app = Flask(__name__)
flask_app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24).hex())

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin"):
            return redirect("/admin/login")
        return f(*args, **kwargs)
    return decorated

def get_stats(keys):
    now = datetime.utcnow()
    used_count  = sum(1 for v in keys.values() if v.get("used"))
    available   = sum(1 for v in keys.values() if not v.get("used"))
    soon = now + timedelta(days=3)
    expiring_soon = sum(1 for v in keys.values()
                        if datetime.fromisoformat(v["expires"]) <= soon)
    return used_count, available, expiring_soon

@flask_app.route("/")
def index():
    keys = clean_expired()
    used_count, available, _ = get_stats(keys)
    return render_template_string(PUBLIC_HTML, keys=keys,
                                  total=len(keys), used_count=used_count, available=available)

@flask_app.route("/admin")
@login_required
def admin():
    keys = clean_expired()
    used_count, available, expiring_soon = get_stats(keys)
    return render_template_string(ADMIN_HTML, keys=keys, total=len(keys),
                                  used_count=used_count, available=available,
                                  expiring_soon=expiring_soon)

@flask_app.route("/admin/login", methods=["GET","POST"])
def admin_login():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect("/admin")
        return render_template_string(LOGIN_HTML, error="Senha incorreta.")
    return render_template_string(LOGIN_HTML, error=None)

@flask_app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect("/")

@flask_app.route("/admin/api/toggle-used", methods=["POST"])
@login_required
def api_toggle_used():
    data = request.get_json()
    key  = data.get("key","").strip().upper()
    keys = load_keys()
    if key not in keys:
        return jsonify(ok=False, error="not found"), 404
    keys[key]["used"] = not keys[key].get("used", False)
    save_keys(keys)
    return jsonify(ok=True, used=keys[key]["used"])

@flask_app.route("/admin/api/delete-key", methods=["POST"])
@login_required
def api_delete_key():
    data = request.get_json()
    key  = data.get("key","").strip().upper()
    keys = load_keys()
    if key not in keys:
        return jsonify(ok=False, error="not found"), 404
    del keys[key]
    save_keys(keys)
    return jsonify(ok=True)

@flask_app.route("/keys")
def keys_json():
    """Endpoint consumido pelo loader C++ para validar keys."""
    keys = clean_expired()
    return {"keys": list(keys.keys())}, 200

@flask_app.route("/health")
def health():
    return {"status": "ok", "keys": len(load_keys())}, 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host="0.0.0.0", port=port, use_reloader=False)

# =========================
# DISCORD BOT
# =========================
intents = discord.Intents.default()
intents.guilds  = True
intents.members = True

bot  = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

def is_admin(interaction: discord.Interaction) -> bool:
    if not ADMIN_ROLE_ID:
        return interaction.user.guild_permissions.administrator
    return any(r.id == ADMIN_ROLE_ID for r in interaction.user.roles)

def error_embed(msg: str) -> discord.Embed:
    return discord.Embed(description=f"❌ {msg}", color=0xef4444)

def success_embed(title: str) -> discord.Embed:
    return discord.Embed(title=title, color=0x7c3aed)

# ── on_ready ──────────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    log.info(f"Logado como {bot.user} (ID: {bot.user.id})")
    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.watching, name="WhiteKey")
    )

    # Sync instantâneo se GUILD_ID estiver definido (recomendado para produção)
    if GUILD_ID:
        guild = discord.Object(id=int(GUILD_ID))
        tree.copy_global_to(guild=guild)
        await tree.sync(guild=guild)
        log.info(f"Comandos sincronizados no servidor {GUILD_ID} ✅")
    else:
        await tree.sync()
        log.info("Comandos sincronizados globalmente (pode levar até 1h) ⏳")
        log.warning("Dica: defina GUILD_ID nas env vars para sync instantâneo!")

# ── /createkey ────────────────────────────────────────────────────────────────
@tree.command(name="createkey", description="Criar uma nova key de acesso")
@app_commands.describe(duracao="Ex: 7d, 30d, 3m, 1a, 12h")
async def createkey(interaction: discord.Interaction, duracao: str):
    if not is_admin(interaction):
        return await interaction.response.send_message(embed=error_embed("Você não tem permissão."), ephemeral=True)

    delta = parse_duration(duracao)
    if not delta:
        return await interaction.response.send_message(
            embed=error_embed("Duração inválida. Use: `7d`, `30d`, `3m`, `1a`, `12h`"),
            ephemeral=True
        )

    now     = datetime.utcnow()
    expires = now + delta
    key     = generate_key()
    keys    = load_keys()
    keys[key] = {
        "expires":    expires.isoformat(),
        "created_by": interaction.user.id,
        "created_at": now.isoformat(),
    }
    save_keys(keys)

    embed = success_embed("🔑 Key Criada com Sucesso")
    embed.add_field(name="Key", value=f"```{key}```", inline=False)
    embed.add_field(name="Expira em",   value=f"<t:{int(expires.timestamp())}:F>", inline=True)
    embed.add_field(name="Criada por",  value=interaction.user.mention, inline=True)
    embed.set_footer(text=f"Total de keys ativas: {len(keys)}")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ── /deletekey ────────────────────────────────────────────────────────────────
@tree.command(name="deletekey", description="Remover uma key existente")
@app_commands.describe(key="A key a ser removida (ex: WHITE-XXXX-XXXX-XXXX)")
async def deletekey(interaction: discord.Interaction, key: str):
    if not is_admin(interaction):
        return await interaction.response.send_message(embed=error_embed("Você não tem permissão."), ephemeral=True)

    keys = load_keys()
    key  = key.strip().upper()
    if key not in keys:
        return await interaction.response.send_message(embed=error_embed("Key não encontrada."), ephemeral=True)

    del keys[key]
    save_keys(keys)

    embed = success_embed("🗑️ Key Removida")
    embed.add_field(name="Key", value=f"```{key}```", inline=False)
    embed.set_footer(text=f"Keys restantes: {len(keys)}")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ── /listkeys ─────────────────────────────────────────────────────────────────
@tree.command(name="listkeys", description="Listar todas as keys ativas")
async def listkeys(interaction: discord.Interaction):
    if not is_admin(interaction):
        return await interaction.response.send_message(embed=error_embed("Você não tem permissão."), ephemeral=True)

    keys = clean_expired()
    embed = success_embed(f"📋 Keys Ativas ({len(keys)})")

    if not keys:
        embed.description = "Nenhuma key ativa no momento."
    else:
        lines = []
        for k, v in list(keys.items())[:15]:   # máx 15 para não estourar embed
            exp_ts = int(datetime.fromisoformat(v["expires"]).timestamp())
            lines.append(f"`{k}` — <t:{exp_ts}:d>")
        embed.description = "\n".join(lines)
        if len(keys) > 15:
            embed.set_footer(text=f"... e mais {len(keys)-15} keys. Veja o dashboard completo.")

    await interaction.response.send_message(embed=embed, ephemeral=True)

# ── /checkkey ─────────────────────────────────────────────────────────────────
@tree.command(name="checkkey", description="Verificar se uma key é válida")
@app_commands.describe(key="A key a verificar")
async def checkkey(interaction: discord.Interaction, key: str):
    keys = clean_expired()
    key  = key.strip().upper()

    if key in keys:
        exp_ts = int(datetime.fromisoformat(keys[key]["expires"]).timestamp())
        embed  = success_embed("✅ Key Válida")
        embed.add_field(name="Key",    value=f"```{key}```", inline=False)
        embed.add_field(name="Expira", value=f"<t:{exp_ts}:F>", inline=False)
    else:
        embed = error_embed("Key inválida ou expirada.")

    await interaction.response.send_message(embed=embed, ephemeral=True)

# =========================
# INICIALIZAÇÃO
# =========================
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    log.info("Flask iniciado em background.")
    bot.run(BOT_TOKEN, log_handler=None)
