import discord
from discord.ext import commands
from discord import app_commands
from flask import Flask, jsonify
import json, random, string, threading
from datetime import datetime, timedelta

ADMIN_ROLE_ID = 1467560515101392998
BOT_TOKEN = "MTQ3MzMyODMwMjM3MzYwNTUyOQ.GOGwoE.bc4oowJ4nByA_PsbruvL_tmZN5m-PUzSkyVLLQ"  # TROCA PELO NOVO TOKEN!

app = Flask(__name__)

def load_keys():
    try:
        with open("keys.json", "r") as f:
            return json.load(f)
    except:
        return {}

def save_keys(keys):
    with open("keys.json", "w") as f:
        json.dump(keys, f, indent=2)

def generate_key():
    def part():
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"WHITE-{part()}-{part()}-{part()}"

def clean_expired_keys():
    keys = load_keys()
    now = datetime.utcnow().isoformat()
    cleaned = {k: v for k, v in keys.items() if v["expires"] > now}
    save_keys(cleaned)
    return cleaned

# Rota que o C++ consulta — retorna só as keys válidas
@app.route("/keys")
def get_keys():
    keys = clean_expired_keys()
    return jsonify(list(keys.keys()))

def run_flask():
    app.run(host="0.0.0.0", port=8080)

intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

@bot.event
async def on_ready():
    await tree.sync()
    print(f"Bot online: {bot.user}")

def is_admin(interaction: discord.Interaction):
    return any(r.id == ADMIN_ROLE_ID for r in interaction.user.roles)

@tree.command(name="createkey", description="Cria uma nova key com duração")
@app_commands.describe(duracao="Duração: 7d, 30d, 3m, 6m, 1a, 2a")
async def createkey(interaction: discord.Interaction, duracao: str):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Sem permissão!", ephemeral=True)
        return

    now = datetime.utcnow()
    duracao = duracao.lower().strip()

    if duracao.endswith("d"):
        delta = timedelta(days=int(duracao[:-1]))
    elif duracao.endswith("m"):
        delta = timedelta(days=int(duracao[:-1]) * 30)
    elif duracao.endswith("a"):
        delta = timedelta(days=int(duracao[:-1]) * 365)
    else:
        await interaction.response.send_message("❌ Formato inválido! Use: `7d`, `30d`, `3m`, `6m`, `1a`, `2a`", ephemeral=True)
        return

    expires = (now + delta).isoformat()
    expires_br = (now + delta).strftime("%d/%m/%Y")

    keys = load_keys()
    key = generate_key()
    keys[key] = {
        "expires": expires,
        "created": now.isoformat()
    }
    save_keys(keys)

    await interaction.response.send_message(
        f"✅ Key criada!\n```{key}```\n📅 Expira em: `{expires_br}`",
        ephemeral=True
    )

@tree.command(name="deletekey", description="Deleta uma key")
async def deletekey(interaction: discord.Interaction, key: str):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Sem permissão!", ephemeral=True)
        return
    keys = load_keys()
    if key in keys:
        del keys[key]
        save_keys(keys)
        await interaction.response.send_message(f"✅ Key deletada: `{key}`", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Key não encontrada!", ephemeral=True)

@tree.command(name="listkeys", description="Lista todas as keys ativas")
async def listkeys(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Sem permissão!", ephemeral=True)
        return
    keys = clean_expired_keys()
    if not keys:
        await interaction.response.send_message("Nenhuma key ativa.", ephemeral=True)
        return
    lista = "\n".join([
        f"`{k}` — expira {datetime.fromisoformat(v['expires']).strftime('%d/%m/%Y')}"
        for k, v in keys.items()
    ])
    await interaction.response.send_message(f"**🔑 Keys ativas ({len(keys)}):**\n{lista}", ephemeral=True)

@tree.command(name="checkkey", description="Verifica se uma key é válida")
async def checkkey(interaction: discord.Interaction, key: str):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Sem permissão!", ephemeral=True)
        return
    keys = clean_expired_keys()
    if key in keys:
        expires = datetime.fromisoformat(keys[key]["expires"]).strftime("%d/%m/%Y")
        await interaction.response.send_message(f"✅ Key válida! Expira em: `{expires}`", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Key inválida ou expirada!", ephemeral=True)

@tree.command(name="clearkeys", description="Deleta TODAS as keys")
async def clearkeys(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Sem permissão!", ephemeral=True)
        return
    save_keys({})
    await interaction.response.send_message("✅ Todas as keys deletadas!", ephemeral=True)

threading.Thread(target=run_flask, daemon=True).start()
bot.run(BOT_TOKEN)


