import discord
from discord.ext import commands
from discord import app_commands
from flask import Flask, jsonify
import json, random, string, threading

# ==============================
# CONFIGURAÇÕES — edite aqui
ADMIN_ROLE_ID = 123456789  # ID do cargo admin do seu servidor
BOT_TOKEN = "MTQ3MzMyODMwMjM3MzYwNTUyOQ.GOGwoE.bc4oowJ4nByA_PsbruvL_tmZN5m-PUzSkyVLLQ"
# ==============================

# Flask pra expor as keys como URL
app = Flask(__name__)

def load_keys():
    try:
        with open("keys.json", "r") as f:
            return json.load(f)
    except:
        return []

def save_keys(keys):
    with open("keys.json", "w") as f:
        json.dump(keys, f)

def generate_key():
    def part():
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"WHITE-{part()}-{part()}-{part()}"

# Rota que o C++ vai consultar
@app.route("/keys")
def get_keys():
    return jsonify(load_keys())

def run_flask():
    app.run(host="0.0.0.0", port=8080)

# Bot Discord
intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

@bot.event
async def on_ready():
    await tree.sync()
    print(f"Bot online: {bot.user}")

def is_admin(interaction: discord.Interaction):
    return any(r.id == ADMIN_ROLE_ID for r in interaction.user.roles)

@tree.command(name="createkey", description="Cria uma nova key")
async def createkey(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Sem permissão!", ephemeral=True)
        return
    keys = load_keys()
    key = generate_key()
    keys.append(key)
    save_keys(keys)
    await interaction.response.send_message(
        f"✅ Key criada com sucesso!\n```{key}```", ephemeral=True
    )

@tree.command(name="deletekey", description="Deleta uma key")
async def deletekey(interaction: discord.Interaction, key: str):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Sem permissão!", ephemeral=True)
        return
    keys = load_keys()
    if key in keys:
        keys.remove(key)
        save_keys(keys)
        await interaction.response.send_message(f"✅ Key deletada: `{key}`", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Key não encontrada!", ephemeral=True)

@tree.command(name="listkeys", description="Lista todas as keys ativas")
async def listkeys(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Sem permissão!", ephemeral=True)
        return
    keys = load_keys()
    if not keys:
        await interaction.response.send_message("Nenhuma key cadastrada.", ephemeral=True)
        return
    lista = "\n".join([f"`{k}`" for k in keys])
    await interaction.response.send_message(f"**🔑 Keys ativas ({len(keys)}):**\n{lista}", ephemeral=True)

@tree.command(name="checkkey", description="Verifica se uma key é válida")
async def checkkey(interaction: discord.Interaction, key: str):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Sem permissão!", ephemeral=True)
        return
    keys = load_keys()
    if key in keys:
        await interaction.response.send_message(f"✅ Key válida!", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ Key inválida!", ephemeral=True)

@tree.command(name="clearkeys", description="Deleta TODAS as keys")
async def clearkeys(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Sem permissão!", ephemeral=True)
        return
    save_keys([])
    await interaction.response.send_message("✅ Todas as keys deletadas!", ephemeral=True)

# Inicia Flask em thread separada e bot
threading.Thread(target=run_flask, daemon=True).start()
bot.run(BOT_TOKEN)
