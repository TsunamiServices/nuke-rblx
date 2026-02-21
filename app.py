import discord
from discord import app_commands
from flask import Flask, render_template_string
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
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>WhiteKey Dashboard</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Segoe UI', sans-serif;
    background: #0f0f13;
    color: #e2e8f0;
    min-height: 100vh;
    padding: 2rem;
  }
  h1 {
    font-size: 1.8rem;
    font-weight: 700;
    background: linear-gradient(135deg, #7c3aed, #3b82f6);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0.4rem;
  }
  .subtitle { color: #64748b; margin-bottom: 2rem; font-size: 0.9rem; }
  .stats {
    display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 2rem;
  }
  .stat-card {
    background: #1e1e2e;
    border: 1px solid #2a2a3e;
    border-radius: 12px;
    padding: 1rem 1.5rem;
    min-width: 140px;
  }
  .stat-card .num { font-size: 2rem; font-weight: 700; color: #7c3aed; }
  .stat-card .lbl { font-size: 0.78rem; color: #64748b; text-transform: uppercase; letter-spacing: .05em; }
  table { width: 100%; border-collapse: collapse; }
  thead tr { background: #1e1e2e; }
  th {
    padding: .75rem 1rem; text-align: left; font-size: .78rem;
    text-transform: uppercase; letter-spacing: .07em; color: #64748b;
  }
  tbody tr { border-bottom: 1px solid #1e1e2e; transition: background .15s; }
  tbody tr:hover { background: #1a1a28; }
  td { padding: .75rem 1rem; font-size: .88rem; }
  .key-val { font-family: monospace; color: #a78bfa; }
  .badge {
    display: inline-block; padding: 2px 10px; border-radius: 20px;
    font-size: .75rem; font-weight: 600;
  }
  .badge-ok  { background: #14532d55; color: #4ade80; border: 1px solid #166534; }
  .badge-exp { background: #7f1d1d55; color: #f87171; border: 1px solid #991b1b; }
  .empty { text-align: center; padding: 3rem; color: #4a5568; }
  .container { max-width: 900px; margin: 0 auto; }
</style>
</head>
<body>
<div class="container">
  <h1>⬡ WhiteKey</h1>
  <p class="subtitle">Painel de gerenciamento de keys — atualizado em tempo real</p>

  <div class="stats">
    <div class="stat-card">
      <div class="num">{{ keys|length }}</div>
      <div class="lbl">Keys ativas</div>
    </div>
  </div>

  {% if keys %}
  <table>
    <thead>
      <tr>
        <th>Key</th>
        <th>Expira</th>
        <th>Status</th>
      </tr>
    </thead>
    <tbody>
    {% for k, v in keys.items() %}
      <tr>
        <td class="key-val">{{ k }}</td>
        <td>{{ v.expires[:10] }}</td>
        <td><span class="badge badge-ok">✓ Ativa</span></td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
  {% else %}
    <p class="empty">Nenhuma key ativa no momento.</p>
  {% endif %}
</div>
</body>
</html>
"""

flask_app = Flask(__name__)

@flask_app.route("/")
def index():
    keys = clean_expired()
    return render_template_string(DASHBOARD_HTML, keys=keys)

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
