# bot.py - FIXED: Currency System (K, M, B, T, Qa, Qi, Sx, Sp, Oc)
import discord
from discord import app_commands
from discord.ext import commands
import os
import json
import re

# ============================
# CONFIG
# ============================
TOKEN = "MTQyMTE1NzQ2MzM1NjM0MjMzMw.G5pz3W.QpbrYjYXANG6u5UJ5_dKfi4Uoq8Uu-KCjL5Z8s"  # ⚠️ Replace this, never share your real token!
GUILD_ID = 1427269750576124007
OWNER_ID = 1184517618749669510
TICKET_CATEGORY_NAME = "tickets"
PANEL_FILE = "data.json"
STATUS_CHANNEL_ID = 1427304360484012053

ADMIN_ROLE_IDS = {
    1427270463305945172,  # Owner role
    1427294002662736046,
}

# ============================
# Persistence
# ============================
def ensure_data():
    if not os.path.exists(PANEL_FILE):
        base = {
            "ticket_counter": 0,
            "balances": {},
            "usernames": {},
            "links": {},
            "invites": {},
            "panel": None
        }
        with open(PANEL_FILE, "w") as f:
            json.dump(base, f, indent=2)
        return base
    with open(PANEL_FILE, "r") as f:
        return json.load(f)

def save_data():
    with open(PANEL_FILE, "w") as f:
        json.dump(data, f, indent=2)

data = ensure_data()

# ============================
# Bot setup
# ============================
intents = discord.Intents.default()
intents.members = True
intents.guilds = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

def is_admin(user: discord.Member):
    return user.id == OWNER_ID or any(r.id in ADMIN_ROLE_IDS for r in user.roles)

# ============================
# Currency Helpers
# ============================
suffixes = [
    (1e27, "Oc"), (1e24, "Sp"), (1e21, "Sx"), (1e18, "Qi"),
    (1e15, "Qa"), (1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")
]

def format_balance(amount: float) -> str:
    """Formats large numbers with suffixes (K, M, B, T, Qa, Qi, Sx, Sp, Oc)."""
    for value, suffix in suffixes:
        if amount >= value:
            formatted = f"{amount / value:.2f}".rstrip("0").rstrip(".")
            return f"{formatted}{suffix}"
    return str(int(amount))

def parse_amount(input_str: str) -> float:
    """Parses input like 1k, 1M, 1Qa into actual numbers."""
    input_str = input_str.strip().lower()
    match = re.match(r"^([\d,.]+)\s*([a-z]*)$", input_str)
    if not match:
        raise ValueError("Invalid amount format.")
    num, suffix = match.groups()
    num = float(num.replace(",", ""))
    suffix = suffix.lower()

    suffix_map = {
        "k": 1e3,
        "m": 1e6,
        "b": 1e9,
        "t": 1e12,
        "qa": 1e15,
        "qi": 1e18,
        "sx": 1e21,
        "sp": 1e24,
        "oc": 1e27
    }
    if suffix in suffix_map:
        num *= suffix_map[suffix]
    return num

# ============================
# Panel / Tickets / Misc
# ============================
async def update_panel_status(status_text: str):
    panel = data.get("panel")
    if not panel:
        return
    guild = bot.get_guild(panel["guild"])
    if not guild:
        return
    channel = guild.get_channel(panel["channel"])
    if not channel:
        return
    try:
        msg = await channel.fetch_message(panel["message"])
        if msg.embeds:
            embed = msg.embeds[0]
            if embed.fields:
                embed.set_field_at(0, name="Bot Status", value=status_text, inline=False)
            else:
                embed.add_field(name="Bot Status", value=status_text, inline=False)
            await msg.edit(embed=embed, view=TicketView())
    except:
        pass

class HandleTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔧 Handle Ticket", style=discord.ButtonStyle.primary, custom_id="handle_ticket_btn")
    async def handle_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await interaction.channel.send(f"✅ {interaction.user.mention} is now handling this ticket.")

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎟️ Create Ticket", style=discord.ButtonStyle.green, custom_id="create_ticket_btn")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        data["ticket_counter"] += 1
        ticket_number = str(data["ticket_counter"]).zfill(3)

        category = discord.utils.get(interaction.guild.categories, name=TICKET_CATEGORY_NAME)
        if not category:
            category = await interaction.guild.create_category(TICKET_CATEGORY_NAME)

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True),
            interaction.guild.me: discord.PermissionOverwrite(view_channel=True),
        }
        channel = await interaction.guild.create_text_channel(
            name=f"ticket-{ticket_number}", overwrites=overwrites, category=category
        )

        invites = data["invites"].get(str(interaction.user.id), 0)
        balance = data["balances"].get(str(interaction.user.id), 0)

        embed = discord.Embed(
            title=f"🎫 Ticket #{ticket_number}",
            description=f"{interaction.user.mention} created this ticket.",
            color=discord.Color.blurple()
        )
        embed.add_field(name="📩 Invites", value=f"{invites}", inline=False)
        embed.add_field(name="💰 Balance", value=format_balance(balance), inline=False)

        await channel.send(embed=embed, view=HandleTicketView())
        save_data()
        await interaction.followup.send(f"✅ Ticket created: {channel.mention}", ephemeral=True)

# ============================
# Slash commands
# ============================
@tree.command(name="tickets_show", description="Show ticket panel", guild=discord.Object(id=GUILD_ID))
async def tickets_show(interaction: discord.Interaction):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("❌ No permission.", ephemeral=True)
    embed = discord.Embed(title="🎟️ Ticket Panel",
                          description="Click the button to create a ticket.",
                          color=discord.Color.blue())
    embed.add_field(name="Bot Status", value="🟢 Online", inline=False)
    msg = await interaction.channel.send(embed=embed, view=TicketView())
    data["panel"] = {"guild": interaction.guild.id, "channel": interaction.channel.id, "message": msg.id}
    save_data()
    await interaction.response.send_message("✅ Panel created.", ephemeral=True)

@tree.command(name="balance", description="Check balance", guild=discord.Object(id=GUILD_ID))
async def balance(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    bal = data["balances"].get(str(member.id), 0)
    await interaction.response.send_message(f"💰 {member.mention} has {format_balance(bal)}")

@tree.command(name="add_balance", description="Add balance", guild=discord.Object(id=GUILD_ID))
async def add_balance(interaction: discord.Interaction, member: discord.Member, amount: str):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("❌ No permission.", ephemeral=True)
    try:
        amount_num = parse_amount(amount)
    except Exception:
        return await interaction.response.send_message("❌ Invalid amount format. Try `1K`, `1M`, `1Qa`, etc.", ephemeral=True)

    data["balances"][str(member.id)] = data["balances"].get(str(member.id), 0) + amount_num
    save_data()
    await interaction.response.send_message(f"✅ Added {format_balance(amount_num)} to {member.mention}")

@tree.command(name="remove_balance", description="Remove balance", guild=discord.Object(id=GUILD_ID))
async def remove_balance(interaction: discord.Interaction, member: discord.Member, amount: str):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("❌ No permission.", ephemeral=True)
    try:
        amount_num = parse_amount(amount)
    except Exception:
        return await interaction.response.send_message("❌ Invalid amount format. Try `1K`, `1M`, `1Qa`, etc.", ephemeral=True)

    data["balances"][str(member.id)] = max(0, data["balances"].get(str(member.id), 0) - amount_num)
    save_data()
    await interaction.response.send_message(f"✅ Removed {format_balance(amount_num)} from {member.mention}")

@tree.command(name="link_set", description="Set your link", guild=discord.Object(id=GUILD_ID))
async def link_set(interaction: discord.Interaction, link: str):
    data["links"][str(interaction.user.id)] = link
    save_data()
    await interaction.response.send_message(f"✅ Saved your link: {link}")

@tree.command(name="link_get", description="Get a user's link", guild=discord.Object(id=GUILD_ID))
async def link_get(interaction: discord.Interaction, member: discord.Member):
    link = data["links"].get(str(member.id))
    if not link:
        return await interaction.response.send_message("❌ No link found.")
    await interaction.response.send_message(f"🔗 {member.mention}'s link: {link}")

@tree.command(name="username_set", description="Set your username", guild=discord.Object(id=GUILD_ID))
async def username_set(interaction: discord.Interaction, username: str):
    data["usernames"][str(interaction.user.id)] = username
    save_data()
    await interaction.response.send_message(f"✅ Username saved: {username}")

@tree.command(name="username_get", description="Get a user's username", guild=discord.Object(id=GUILD_ID))
async def username_get(interaction: discord.Interaction, member: discord.Member):
    uname = data["usernames"].get(str(member.id))
    if not uname:
        return await interaction.response.send_message("❌ No username found.")
    await interaction.response.send_message(f"👤 {member.mention}'s username: {uname}")

@tree.command(name="claim", description="Claim rewards (reset invites)", guild=discord.Object(id=GUILD_ID))
async def claim(interaction: discord.Interaction):
    data["invites"][str(interaction.user.id)] = 0
    save_data()
    await interaction.response.send_message("✅ Your invites have been reset to 0.")

@tree.command(name="close_ticket", description="Close the current ticket", guild=discord.Object(id=GUILD_ID))
async def close_ticket(interaction: discord.Interaction):
    if not interaction.channel.name.startswith("ticket-"):
        return await interaction.response.send_message("❌ This isn’t a ticket channel.", ephemeral=True)
    await interaction.channel.delete()

# ============================
# Events
# ============================
@bot.event
async def on_ready():
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    bot.add_view(TicketView())
    bot.add_view(HandleTicketView())
    await update_panel_status("🟢 Online")
    ch = bot.get_channel(STATUS_CHANNEL_ID)
    if ch:
        await ch.send("🟢 Bot is **online**!")
    print(f"✅ Logged in as {bot.user}")

@bot.event
async def on_disconnect():
    await update_panel_status("🔴 Offline")
    ch = bot.get_channel(STATUS_CHANNEL_ID)
    if ch:
        await ch.send("🔴 Bot is **offline**!")

# ============================
# Run
# ============================
bot.run(TOKEN)
