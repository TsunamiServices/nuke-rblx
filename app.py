import discord
from discord import app_commands
from flask import Flask, jsonify, request
import json, random, string, threading, os
from datetime import datetime, timedelta

# ========================
# ENV CONFIG
# ========================

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ROLE_ID = int(os.environ.get("ADMIN_ROLE_ID", 0))
API_SECRET = os.environ.get("API_SECRET")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN nao encontrado!")

if not API_SECRET:
    raise RuntimeError("API_SECRET nao encontrado!")

# ========================
# FLASK API
# ========================

app = Flask(__name__)

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

def clean_expired_keys():
    keys = load_keys()
    now = datetime.utcnow()
    cleaned = {}

    for k, v in keys.items():
        exp = datetime.fromisoformat(v["expires"])
        if exp > now:
            cleaned[k] = v

    save_keys(cleaned)
    return cleaned

@app.route("/keys")
def get_keys():
    if request.headers.get("Authorization") != API_SECRET:
        return jsonify({"error": "unauthorized"}), 403
    keys = clean_expired_keys()
    return jsonify(keys)

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ========================
# DISCORD BOT
# ========================

intents = discord.Intents.default()
intents.guilds = True
intents.members = True

bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

def is_admin(interaction: discord.Interaction):
    return any(r.id == ADMIN_ROLE_ID for r in interaction.user.roles)

def duration_to_timedelta(duracao: str):
    duracao = duracao.lower().strip()
    if duracao.endswith("d"):
        return timedelta(days=int(duracao[:-1]))
    elif duracao.endswith("m"):
        return timedelta(days=int(duracao[:-1]) * 30)
    elif duracao.endswith("a"):
        return timedelta(days=int(duracao[:-1]) * 365)
    return None

@bot.event
async def on_ready():
    await tree.sync()
    print(f"Bot online: {bot.user}")

# ========================
# CREATE KEY
# ========================

@tree.command(name="createkey", description="Cria uma nova key")
@app_commands.describe(duracao="Ex: 7d, 30d, 3m, 1a")
async def createkey(interaction: discord.Interaction, duracao: str):

    if not is_admin(interaction):
        return await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)

    delta = duration_to_timedelta(duracao)
    if not delta:
        return await interaction.response.send_message("❌ Formato inválido. Use 7d, 30d, 3m, 1a.", ephemeral=True)

    now = datetime.utcnow()
    expires = now + delta

    keys = load_keys()
    key = generate_key()

    keys[key] = {
        "created": now.isoformat(),
        "expires": expires.isoformat(),
        "created_by": interaction.user.id
    }

    save_keys(keys)

    embed = discord.Embed(
        title="🔑 Nova Key Criada",
        color=discord.Color.green(),
        timestamp=datetime.utcnow()
    )

    embed.add_field(name="Key", value=f"`{key}`", inline=False)
    embed.add_field(name="Expira em", value=expires.strftime("%d/%m/%Y"), inline=True)
    embed.add_field(name="Criada por", value=interaction.user.mention, inline=True)
    embed.set_footer(text="Sistema de Licenças")

    await interaction.response.send_message(embed=embed, ephemeral=True)

# ========================
# DELETE KEY
# ========================

@tree.command(name="deletekey", description="Deleta uma key")
async def deletekey(interaction: discord.Interaction, key: str):

    if not is_admin(interaction):
        return await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)

    keys = load_keys()

    if key not in keys:
        return await interaction.response.send_message("❌ Key não encontrada.", ephemeral=True)

    del keys[key]
    save_keys(keys)

    embed = discord.Embed(
        title="🗑️ Key Removida",
        description=f"Key `{key}` foi deletada.",
        color=discord.Color.red(),
        timestamp=datetime.utcnow()
    )

    await interaction.response.send_message(embed=embed, ephemeral=True)

# ========================
# LIST KEYS
# ========================

@tree.command(name="listkeys", description="Lista keys ativas")
async def listkeys(interaction: discord.Interaction):

    if not is_admin(interaction):
        return await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)

    keys = clean_expired_keys()

    if not keys:
        return await interaction.response.send_message("Nenhuma key ativa.", ephemeral=True)

    embed = discord.Embed(
        title="📋 Keys Ativas",
        color=discord.Color.blurple(),
        timestamp=datetime.utcnow()
    )

    for k, v in keys.items():
        exp = datetime.fromisoformat(v["expires"])
        embed.add_field(
            name=k,
            value=f"Expira: {exp.strftime('%d/%m/%Y')}",
            inline=False
        )

    embed.set_footer(text=f"Total: {len(keys)}")

    await interaction.response.send_message(embed=embed, ephemeral=True)

# ========================
# CHECK KEY
# ========================

@tree.command(name="checkkey", description="Verifica uma key")
async def checkkey(interaction: discord.Interaction, key: str):

    if not is_admin(interaction):
        return await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)

    keys = clean_expired_keys()

    if key not in keys:
        return await interaction.response.send_message("❌ Key inválida ou expirada.", ephemeral=True)

    exp = datetime.fromisoformat(keys[key]["expires"])

    embed = discord.Embed(
        title="✅ Key Válida",
        color=discord.Color.green(),
        timestamp=datetime.utcnow()
    )

    embed.add_field(name="Key", value=f"`{key}`", inline=False)
    embed.add_field(name="Expira em", value=exp.strftime("%d/%m/%Y"), inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)

# ========================
# CLEAR KEYS
# ========================

@tree.command(name="clearkeys", description="Remove todas as keys")
async def clearkeys(interaction: discord.Interaction):

    if not is_admin(interaction):
        return await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)

    save_keys({})

    embed = discord.Embed(
        title="⚠️ Todas as Keys Foram Removidas",
        color=discord.Color.orange(),
        timestamp=datetime.utcnow()
    )

    await interaction.response.send_message(embed=embed, ephemeral=True)

# ========================
# START
# ========================

threading.Thread(target=run_flask, daemon=True).start()
bot.run(BOT_TOKEN)
