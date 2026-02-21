import discord
from discord import app_commands
from flask import Flask, render_template
import json, random, string, threading, os
from datetime import datetime, timedelta

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ROLE_ID = int(os.environ.get("ADMIN_ROLE_ID", 0))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN nao encontrado!")

# =========================
# DATABASE (JSON SIMPLES)
# =========================

def load_keys():
    try:
        with open("keys.json", "r") as f:
            return json.load(f)
    except:
        return {}

def save_keys(keys):
    with open("keys.json", "w") as f:
        json.dump(keys, f, indent=4)

def generate_key():
    def part():
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"WHITE-{part()}-{part()}-{part()}"

def clean_expired():
    keys = load_keys()
    now = datetime.utcnow()
    valid = {}

    for k, v in keys.items():
        if datetime.fromisoformat(v["expires"]) > now:
            valid[k] = v

    save_keys(valid)
    return valid

# =========================
# FLASK SITE
# =========================

app = Flask(__name__)

@app.route("/")
def index():
    keys = clean_expired()
    return render_template("index.html", keys=keys)

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# =========================
# DISCORD BOT
# =========================

intents = discord.Intents.default()
intents.guilds = True
intents.members = True

bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

def is_admin(interaction: discord.Interaction):
    return any(r.id == ADMIN_ROLE_ID for r in interaction.user.roles)

def parse_duration(d):
    d = d.lower()
    if d.endswith("d"):
        return timedelta(days=int(d[:-1]))
    if d.endswith("m"):
        return timedelta(days=int(d[:-1]) * 30)
    if d.endswith("a"):
        return timedelta(days=int(d[:-1]) * 365)
    return None

@bot.event
async def on_ready():
    await tree.sync()
    print("Bot online.")

@tree.command(name="createkey", description="Criar nova key")
async def createkey(interaction: discord.Interaction, duracao: str):

    if not is_admin(interaction):
        return await interaction.response.send_message("Sem permissão.", ephemeral=True)

    delta = parse_duration(duracao)
    if not delta:
        return await interaction.response.send_message("Use: 7d, 30d, 3m, 1a", ephemeral=True)

    now = datetime.utcnow()
    expires = now + delta

    keys = load_keys()
    key = generate_key()

    keys[key] = {
        "expires": expires.isoformat(),
        "created_by": interaction.user.id
    }

    save_keys(keys)

    embed = discord.Embed(
        title="Key Criada",
        color=discord.Color.green()
    )

    embed.add_field(name="Key", value=f"`{key}`", inline=False)
    embed.add_field(name="Expira", value=expires.strftime("%d/%m/%Y"))

    await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(name="deletekey", description="Deletar key")
async def deletekey(interaction: discord.Interaction, key: str):

    if not is_admin(interaction):
        return await interaction.response.send_message("Sem permissão.", ephemeral=True)

    keys = load_keys()

    if key not in keys:
        return await interaction.response.send_message("Key não encontrada.", ephemeral=True)

    del keys[key]
    save_keys(keys)

    await interaction.response.send_message("Key removida.", ephemeral=True)

threading.Thread(target=run_flask, daemon=True).start()
bot.run(BOT_TOKEN)
