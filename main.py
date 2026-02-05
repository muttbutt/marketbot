import discord
from discord.ext import tasks, commands
from discord import app_commands
import sqlite3, datetime, zoneinfo, random, feedparser, os
from keep_alive import keep_alive

# --- CONFIG ---
TOKEN = os.environ.get('TOKEN')
CHANNEL_ID = 1234567890 # Replace with your Channel ID
GUILD_ID = 9876543210   # Replace with your Server ID
EST = zoneinfo.ZoneInfo("America/New_York")
STARTING_CASH = 500

ROLES = {0: "In the Hunt", 1000: "Casual Bettor", 2500: "Novice Better", 
         5000: "Keeper of Coin", 7500: "Hail to the King", 10000: "The fucking Best"}

# --- DATABASE ENGINE ---
def db_query(query, params=(), fetch=False):
    conn = sqlite3.connect('market.db')
    c = conn.cursor()
    c.execute(query, params)
    data = c.fetchall() if fetch else None
    conn.commit()
    conn.close()
    return data

def init_db():
    db_query('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance INTEGER)')
    db_query('CREATE TABLE IF NOT EXISTS bets (user_id INTEGER, amount INTEGER, choice TEXT, date TEXT)')
    db_query('CREATE TABLE IF NOT EXISTS history (date TEXT PRIMARY KEY, question TEXT, winner TEXT)')

# --- UI COMPONENTS ---
class BetModal(discord.ui.Modal, title='Place Your Wager'):
    wager = discord.ui.TextInput(label='Amount', placeholder='e.g. 100', min_length=1)
    def __init__(self, choice, balance):
        super().__init__()
        self.choice, self.balance = choice, balance
    async def on_submit(self, interaction: discord.Interaction):
        try:
            amt = int(self.wager.value)
            if amt > self.balance or amt <= 0: raise ValueError
        except:
            return await interaction.response.send_message(f"❌ Invalid! Balance: ${self.balance}", ephemeral=True)
        db_query("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amt, interaction.user.id))
        db_query("INSERT INTO bets VALUES (?, ?, ?, ?)", (interaction.user.id, amt, self.choice, datetime.date.today().isoformat()))
        await interaction.response.send_message(f"✅ Bet of ${amt} on {self.choice} placed!", ephemeral=True)

class BetView(discord.ui.View):
    def __init__(self, label_a: str = "Yes", label_b: str = "No"):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label=label_a, style=discord.ButtonStyle.green, custom_id="btn_a"))
        self.add_item(discord.ui.Button(label=label_b, style=discord.ButtonStyle.red, custom_id="btn_b"))
        self.add_item(discord.ui.Button(label="🏦 Check Balance", style=discord.ButtonStyle.blurple, custom_id="btn_bal"))

    async def interaction_check(self, interaction: discord.Interaction):
        cid = interaction.data['custom_id']
        res = db_query("SELECT balance FROM users WHERE user_id = ?", (interaction.user.id,), fetch=True)
        bal = res[0][0] if res else STARTING_CASH
        if cid == "btn_bal":
            await interaction.response.send_message(f"🏦 Balance: **${bal}**", ephemeral=True)
        else:
            label = next(i.label for i in self.children if i.custom_id == cid)
            await interaction.response.send_modal(BetModal(label, bal))
        return True

# --- BOT ENGINE ---
class MarketBot(commands.Bot):
    def __init__(self):
        # Using "!" as prefix for the sync command
        super().__init__(command_prefix="!", intents=discord.Intents.all())

    async def setup_hook(self):
        init_db()
        self.add_view(BetView()) 

bot = MarketBot()

# --- MANUAL SYNC COMMAND ---
@bot.command()
@commands.is_owner() 
async def sync(ctx):
    # Clear and re-sync specifically to your server for instant UI update
    bot.tree.clear_commands(guild=discord.Object(id=GUILD_ID))
    bot.tree.copy_global_to(guild=discord.Object(id=GUILD_ID))
    await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
    await ctx.send(f"✅ **Hard Sync Complete!** Menu updated for Server: {GUILD_ID}")

# --- THE BET COMMAND WITH TYPE HINTS ---
@bot.tree.command(name="create_bet", description="Admin: Post a bet with custom labels")
@app_commands.checks.has_permissions(administrator=True)
async def create_bet(interaction: discord.Interaction, question: str, answer_a: str = "Yes", answer_b: str = "No"):
    view = BetView(label_a=answer_a, label_b=answer_b)
    embed = discord.Embed(title="⚖️ MARKET OPEN", description=question, color=0x2ecc71)
    embed.add_field(name="Options", value=f"🟢 {answer_a}\n🔴 {answer_b}")
    await interaction.response.send_message(embed=embed, view=view)

keep_alive()
bot.run(TOKEN)











