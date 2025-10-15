# bot.py — Render-stable + Currency/Ticket System
import discord
from discord.ext import commands
import os, json, re, asyncio
from keep_alive import keep_alive  # ✅ keeps app awake on Render

# ============================
# CONFIG
# ============================
TOKEN = os.getenv("TOKEN")  # set this in Render Environment Variables!
if not TOKEN:
    raise ValueError("❌ TOKEN not found — set it in Render Environment Variables!")

GUILD_ID = 1427269750576124007
OWNER_ID = 1184517618749669510
TICKET_CATEGORY_NAME = "tickets"
PANEL_FILE = "data.json"
STATUS_CHANNEL_ID = 1427304360484012053

ADMIN_ROLE_IDS = {1427270463305945172, 1427294002662736046}

# ============================
# DATA
# ============================
def ensure_data():
    if not os.path.exists(PANEL_FILE):
        base = {
            "ticket_counter": 0,
            "balances": {},
            "usernames": {},
            "links": {},
            "invites": {},
            "panel": None,
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
# BOT SETUP
# ============================
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

def is_admin(user: discord.Member):
    return user.id == OWNER_ID or any(r.id in ADMIN_ROLE_IDS for r in user.roles)

# ============================
# BALANCE FORMAT
# ============================
suffixes = [
    (1e27, "Oc"), (1e24, "Sp"), (1e21, "Sx"), (1e18, "Qi"),
    (1e15, "Qa"), (1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")
]

def format_balance(amount: float) -> str:
    for value, suffix in suffixes:
        if amount >= value:
            formatted = f"{amount / value:.2f}".rstrip("0").rstrip(".")
            return f"{formatted}{suffix}"
    return str(int(amount))

def parse_amount(input_str: str) -> float:
    input_str = input_str.strip().lower()
    match = re.match(r"^([\d,.]+)\s*([a-z]*)$", input_str)
    if not match:
        raise ValueError("Invalid format")
    num, suffix = match.groups()
    num = float(num.replace(",", ""))
    mult = {
        "k": 1e3, "m": 1e6, "b": 1e9, "t": 1e12,
        "qa": 1e15, "qi": 1e18, "sx": 1e21,
        "sp": 1e24, "oc": 1e27
    }.get(suffix, 1)
    return num * mult

# ============================
# PANEL + TICKETS
# ============================
async def update_panel_status(text: str):
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
                embed.set_field_at(0, name="Bot Status", value=text, inline=False)
            else:
                embed.add_field(name="Bot Status", value=text, inline=False)
            await msg.edit(embed=embed, view=TicketView())
    except Exception as e:
        print(f"⚠️ update_panel_status error: {e}")

class HandleTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔧 Handle Ticket", style=discord.ButtonStyle.primary, custom_id="handle_ticket_btn")
    async def handle_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await interaction.channel.send(f"✅ {interaction.user.mention} is handling this ticket.")

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎟️ Create Ticket", style=discord.ButtonStyle.green, custom_id="create_ticket_btn")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        data["ticket_counter"] += 1
        ticket_num = str(data["ticket_counter"]).zfill(3)

        category = discord.utils.get(interaction.guild.categories, name=TICKET_CATEGORY_NAME)
        if not category:
            category = await interaction.guild.create_category(TICKET_CATEGORY_NAME)

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True),
            interaction.guild.me: discord.PermissionOverwrite(view_channel=True),
        }
        channel = await interaction.guild.create_text_channel(
            name=f"ticket-{ticket_num}", overwrites=overwrites, category=category
        )

        invites = data["invites"].get(str(interaction.user.id), 0)
        bal = data["balances"].get(str(interaction.user.id), 0)

        embed = discord.Embed(
            title=f"🎫 Ticket #{ticket_num}",
            description=f"{interaction.user.mention} created this ticket.",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="📩 Invites", value=str(invites), inline=False)
        embed.add_field(name="💰 Balance", value=format_balance(bal), inline=False)

        await channel.send(embed=embed, view=HandleTicketView())
        save_data()
        await interaction.followup.send(f"✅ Ticket created: {channel.mention}", ephemeral=True)

# ============================
# SLASH COMMANDS
# ============================
@tree.command(name="tickets_show", description="Show ticket panel", guild=discord.Object(id=GUILD_ID))
async def tickets_show(interaction: discord.Interaction):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("❌ No permission", ephemeral=True)
    embed = discord.Embed(title="🎟️ Ticket Panel", description="Click to make a ticket!", color=discord.Color.blue())
    embed.add_field(name="Bot Status", value="🟢 Online", inline=False)
    msg = await interaction.channel.send(embed=embed, view=TicketView())
    data["panel"] = {"guild": interaction.guild.id, "channel": interaction.channel.id, "message": msg.id}
    save_data()
    await interaction.response.send_message("✅ Panel created!", ephemeral=True)

@tree.command(name="balance", description="Check your balance", guild=discord.Object(id=GUILD_ID))
async def balance(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    bal = data["balances"].get(str(member.id), 0)
    await interaction.response.send_message(f"💰 {member.mention} has {format_balance(bal)}")

@tree.command(name="add_balance", description="Add balance", guild=discord.Object(id=GUILD_ID))
async def add_balance(interaction: discord.Interaction, member: discord.Member, amount: str):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("❌ No permission", ephemeral=True)
    try:
        amt = parse_amount(amount)
    except:
        return await interaction.response.send_message("❌ Invalid amount (use 1K, 1M, 1Qa...)", ephemeral=True)
    data["balances"][str(member.id)] = data["balances"].get(str(member.id), 0) + amt
    save_data()
    await interaction.response.send_message(f"✅ Added {format_balance(amt)} to {member.mention}")

@tree.command(name="remove_balance", description="Remove balance", guild=discord.Object(id=GUILD_ID))
async def remove_balance(interaction: discord.Interaction, member: discord.Member, amount: str):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("❌ No permission", ephemeral=True)
    try:
        amt = parse_amount(amount)
    except:
        return await interaction.response.send_message("❌ Invalid amount", ephemeral=True)
    data["balances"][str(member.id)] = max(0, data["balances"].get(str(member.id), 0) - amt)
    save_data()
    await interaction.response.send_message(f"✅ Removed {format_balance(amt)} from {member.mention}")

@tree.command(name="close_ticket", description="Close this ticket", guild=discord.Object(id=GUILD_ID))
async def close_ticket(interaction: discord.Interaction):
    if not interaction.channel.name.startswith("ticket-"):
        return await interaction.response.send_message("❌ Not a ticket.", ephemeral=True)
    await interaction.channel.delete()

# ============================
# EVENTS
# ============================
@bot.event
async def on_ready():
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    bot.add_view(TicketView())
    bot.add_view(HandleTicketView())
    await update_panel_status("🟢 Online")
    print(f"✅ Logged in as {bot.user}")

# ============================
# SAFE START (Render-friendly)
# ============================
async def start_bot():
    keep_alive()
    print("⏳ Starting bot in 10s...")
    await asyncio.sleep(10)
    await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(start_bot())
