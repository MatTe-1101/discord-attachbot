import discord
from discord import app_commands
from discord.ext import commands, tasks
import asyncio
import json
from datetime import datetime

CONFIG_FILE = "config.json"

def load_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except:
        return {
            "block_time": None,
            "unblock_time": None,
            "blocked_role": None,
            "bypass_roles": [],
            "log_channel": None,
            "mod_role": None,
            "excluded_channels": []  # 🔥 AGGIUNTO
        }

def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=4)

config = load_config()

intents = discord.Intents.default()
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# =========================================
# LOGGING INTERNO + LOG CANALE DISCORD
# =========================================

async def debug_log(guild: discord.Guild, message: str):
    print(f"[DEBUG] {message}")
    if config["log_channel"]:
        channel = guild.get_channel(int(config["log_channel"]))
        if channel:
            try:
                await channel.send(f"🔧 **DEBUG:** {message}")
            except:
                pass

# =========================================
# CHECK MOD ROLE
# =========================================

def mod_only():
    async def predicate(interaction: discord.Interaction):
        if not config["mod_role"]:
            await interaction.response.send_message("❌ Il ruolo Mod non è ancora impostato!", ephemeral=True)
            return False
        role = interaction.guild.get_role(int(config["mod_role"]))
        if role not in interaction.user.roles:
            await interaction.response.send_message("❌ Non hai il permesso di usare questo comando.", ephemeral=True)
            return False
        return True
    return app_commands.check(predicate)

# =========================================
# FUNZIONI BLOCCO/SBLOCCO
# =========================================

async def block_attachments(guild: discord.Guild):
    await debug_log(guild, "Inizio funzione block_attachments")
    if not config["blocked_role"]:
        await debug_log(guild, "Nessun ruolo bloccato impostato.")
        return

    role = guild.get_role(int(config["blocked_role"]))
    if role is None:
        await debug_log(guild, "Il ruolo configurato non esiste più.")
        return

    bypass_roles = [guild.get_role(int(r)) for r in config["bypass_roles"]]

    for channel in guild.channels:
        if isinstance(channel, discord.TextChannel):

            # 🔥 NUOVO: CANALE ESCLUSO
            if channel.id in config["excluded_channels"]:
                await debug_log(guild, f"Canale ignorato (escluso): {channel.name}")
                continue

            try:
                overwrites = channel.overwrites_for(role)
                overwrites.attach_files = False
                await channel.set_permissions(role, overwrite=overwrites)
                await debug_log(guild, f"Blocco allegati in {channel.name}")

                for bp in bypass_roles:
                    if bp:
                        ow = channel.overwrites_for(bp)
                        ow.attach_files = True
                        await channel.set_permissions(bp, overwrite=ow)
                        await debug_log(guild, f"Bypass applicato a {bp.name} in {channel.name}")

            except Exception as e:
                await debug_log(guild, f"ERRORE canale {channel.name}: {e}")

    await debug_log(guild, "Blocco completato.")

async def unblock_attachments(guild: discord.Guild):
    await debug_log(guild, "Inizio funzione unblock_attachments")
    if not config["blocked_role"]:
        await debug_log(guild, "Nessun ruolo bloccato impostato.")
        return

    role = guild.get_role(int(config["blocked_role"]))
    if role is None:
        await debug_log(guild, "Il ruolo configurato non esiste più.")
        return

    for channel in guild.channels:
        if isinstance(channel, discord.TextChannel):

            # 🔥 NUOVO: CANALE ESCLUSO
            if channel.id in config["excluded_channels"]:
                await debug_log(guild, f"Canale ignorato (escluso): {channel.name}")
                continue

            try:
                overwrites = channel.overwrites_for(role)
                overwrites.attach_files = None
                await channel.set_permissions(role, overwrite=overwrites)
                await debug_log(guild, f"Sblocco allegati in {channel.name}")
            except Exception as e:
                await debug_log(guild, f"ERRORE canale {channel.name}: {e}")

    await debug_log(guild, "Sblocco completato.")

# =========================================
# SCHEDULER
# =========================================

@tasks.loop(seconds=30)
async def scheduler():
    now = datetime.now().strftime("%H:%M")
    for guild in bot.guilds:
        await debug_log(guild, f"[SCHEDULER] Orario attuale: {now} | Block: {config['block_time']} | Unblock: {config['unblock_time']}")
        if config["block_time"] == now:
            await debug_log(guild, f"[SCHEDULER] MATCH → block_time ({now})")
            await block_attachments(guild)
        if config["unblock_time"] == now:
            await debug_log(guild, f"[SCHEDULER] MATCH → unblock_time ({now})")
            await unblock_attachments(guild)

@bot.event
async def on_ready():
    print(f"Bot connesso come {bot.user}")
    scheduler.start()
    try:
        synced = await bot.tree.sync()
        print(f"Comandi slash sincronizzati: {len(synced)}")
    except Exception as e:
        print(f"Errore sync: {e}")

# =========================================
# COMANDI SLASH
# =========================================

@bot.tree.command(name="set_mod_role", description="Imposta il ruolo che può usare i comandi di configurazione")
async def set_mod_role(interaction: discord.Interaction, role: discord.Role):
    if config["mod_role"]:
        await interaction.response.send_message("❌ Il ruolo Mod è già stato impostato!", ephemeral=True)
        return
    config["mod_role"] = role.id
    save_config(config)
    await interaction.response.send_message(f"✅ Ruolo Mod impostato su {role.name}", ephemeral=True)

# ---------------------
# COMANDI MOD
# ---------------------

@bot.tree.command(name="set_log_channel", description="Imposta il canale per log e debug")
@mod_only()
async def set_log_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    config["log_channel"] = channel.id
    save_config(config)
    await interaction.response.send_message(f"📢 Log channel impostato su {channel.mention}")

@bot.tree.command(name="set_block_time", description="Imposta l'orario di blocco allegati (HH:MM)")
@mod_only()
async def set_block_time(interaction: discord.Interaction, time_string: str):
    time_string = time_string.replace(".", ":")
    try:
        datetime.strptime(time_string, "%H:%M")
    except:
        await interaction.response.send_message("❌ Formato non valido. Usa HH:MM", ephemeral=True)
        return
    config["block_time"] = time_string
    save_config(config)
    await interaction.response.send_message(f"⏰ Orario blocco impostato: **{time_string}**")

@bot.tree.command(name="set_unblock_time", description="Imposta l'orario di sblocco allegati (HH:MM)")
@mod_only()
async def set_unblock_time(interaction: discord.Interaction, time_string: str):
    time_string = time_string.replace(".", ":")
    try:
        datetime.strptime(time_string, "%H:%M")
    except:
        await interaction.response.send_message("❌ Formato non valido. Usa HH:MM", ephemeral=True)
        return
    config["unblock_time"] = time_string
    save_config(config)
    await interaction.response.send_message(f"⏰ Orario sblocco impostato: **{time_string}**")

@bot.tree.command(name="set_blocked_role", description="Imposta il ruolo da bloccare")
@mod_only()
async def set_blocked_role(interaction: discord.Interaction, role: discord.Role):
    config["blocked_role"] = role.id
    save_config(config)
    await interaction.response.send_message(f"🔒 Ruolo bloccato impostato su: **{role.name}**")

@bot.tree.command(name="add_bypass_role", description="Aggiungi un ruolo bypass")
@mod_only()
async def add_bypass_role(interaction: discord.Interaction, role: discord.Role):
    if role.id not in config["bypass_roles"]:
        config["bypass_roles"].append(role.id)
        save_config(config)
    await interaction.response.send_message(f"🟢 Ruolo bypass aggiunto: **{role.name}**")

@bot.tree.command(name="remove_bypass_role", description="Rimuovi un ruolo bypass")
@mod_only()
async def remove_bypass_role(interaction: discord.Interaction, role: discord.Role):
    if role.id in config["bypass_roles"]:
        config["bypass_roles"].remove(role.id)
        save_config(config)
    await interaction.response.send_message(f"🔴 Ruolo bypass rimosso: **{role.name}**")

# ---------------------
# 🔥 NUOVI COMANDI CANALI ESCLUSI
# ---------------------

@bot.tree.command(name="add_excluded_channel", description="Esclude un canale dal blocco/sblocco")
@mod_only()
async def add_excluded_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    if channel.id not in config["excluded_channels"]:
        config["excluded_channels"].append(channel.id)
        save_config(config)
        await interaction.response.send_message(f"🚫 Canale escluso: {channel.mention}")
    else:
        await interaction.response.send_message("⚠️ Questo canale è già escluso.", ephemeral=True)

@bot.tree.command(name="remove_excluded_channel", description="Rimuove un canale dall'esclusione")
@mod_only()
async def remove_excluded_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    if channel.id in config["excluded_channels"]:
        config["excluded_channels"].remove(channel.id)
        save_config(config)
        await interaction.response.send_message(f"♻️ Canale reincluso: {channel.mention}")
    else:
        await interaction.response.send_message("❌ Questo canale non era escluso.", ephemeral=True)

# ---------------------
# Comandi test
# ---------------------

@bot.tree.command(name="test_block", description="Forza manualmente il blocco allegati")
@mod_only()
async def test_block(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    await block_attachments(interaction.guild)
    await interaction.followup.send("🔧 Blocco manuale eseguito!")

@bot.tree.command(name="test_unblock", description="Forza manualmente lo sblocco allegati")
@mod_only()
async def test_unblock(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    await unblock_attachments(interaction.guild)
    await interaction.followup.send("🔧 Sblocco manuale eseguito!")

# ---------------------
# Stato
# ---------------------

@bot.tree.command(name="status", description="Mostra lo stato corrente del bot")
@mod_only()
async def status(interaction: discord.Interaction):
    blocked_role = interaction.guild.get_role(int(config["blocked_role"])) if config["blocked_role"] else None
    bypass_roles = [interaction.guild.get_role(int(r)) for r in config["bypass_roles"] if interaction.guild.get_role(int(r))]
    mod_role = interaction.guild.get_role(int(config["mod_role"])) if config["mod_role"] else None
    log_channel = interaction.guild.get_channel(int(config["log_channel"])) if config["log_channel"] else None
    excluded_channels = [interaction.guild.get_channel(int(c)) for c in config["excluded_channels"] if interaction.guild.get_channel(int(c))]

    embed = discord.Embed(title="📊 Stato Bot", color=discord.Color.blue())
    embed.add_field(name="Ruolo bloccato", value=blocked_role.mention if blocked_role else "❌ Nessuno", inline=False)
    embed.add_field(name="Ruoli bypass", value=", ".join(r.mention for r in bypass_roles) if bypass_roles else "❌ Nessuno", inline=False)
    embed.add_field(name="Orario blocco", value=config["block_time"] if config["block_time"] else "❌ Non impostato", inline=True)
    embed.add_field(name="Orario sblocco", value=config["unblock_time"] if config["unblock_time"] else "❌ Non impostato", inline=True)
    embed.add_field(name="Ruolo Moderatore", value=mod_role.mention if mod_role else "❌ Non impostato", inline=False)
    embed.add_field(name="Canale log", value=log_channel.mention if log_channel else "❌ Non impostato", inline=False)
    embed.add_field(name="Canali esclusi", value=", ".join(c.mention for c in excluded_channels) if excluded_channels else "❌ Nessuno", inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)

# =========================================
# RUN BOT
# =========================================

bot.run("TOKEN") 