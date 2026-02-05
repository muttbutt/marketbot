import discord
from discord.ext import tasks, commands
from discord import app_commands
import sqlite3, datetime, zoneinfo, random, feedparser, os

# --- CONFIG ---
TOKEN = os.getenv('TOKEN')
CHANNEL_ID = 1468975504899178576 # Replace with your Channel ID
GUILD_ID = 1140664003371212830   # Replace with your Server ID
This is the final, polished code. I have updated the BetView to handle dynamic button labels and ensured that the /create_bet command passes your custom answers (like "Yes" and "No") directly to the buttons.

📝 Final Configuration Note
Make sure you have your Bot Token in the Replit Secrets tool with the key TOKEN. Also, double-check that your Guild ID and Channel ID are correct at the top.

The Complete Final Code (main.py)
Python
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
    wager = discord.ui.TextInput(label='Amount', placeholder='How much are you risking?', min_length=1)
    
    def __init__(self, choice, balance):
        super().__init__()
        self.choice = choice
        self.balance = balance

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amt = int(self.wager.value)
            if amt > self.balance or amt <= 0: raise ValueError
        except:
            return await interaction.response.send_message(f"❌ Invalid amount! You only have ${self.balance}.", ephemeral=True)
        
        today = datetime.date.today().isoformat()
        db_query("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amt, interaction.user.id))
        db_query("INSERT INTO bets VALUES (?, ?, ?, ?)", (interaction.user.id, amt, self.choice, today))
        
        new_bal = self.balance - amt
        await interaction.response.send_message(f"✅ Bet of ${amt} placed on **{self.choice}**!\nRemaining Balance: **${new_bal}**", ephemeral=True)

class BetView(discord.ui.View):
    def __init__(self, label_a: str = "Option A", label_b: str = "Option B"):
        super().__init__(timeout=None)
        self.children[0].label = label_a
        self.children[1].label = label_b

    async def onboarding(self, interaction):
        res = db_query("SELECT balance FROM users WHERE user_id = ?", (interaction.user.id,), fetch=True)
        if not res:
            db_query("INSERT INTO users VALUES (?, ?)", (interaction.user.id, STARTING_CASH))
            role = discord.utils.get(interaction.guild.roles, name="In the Hunt")
            if role: await interaction.user.add_roles(role)
            return STARTING_CASH
        return res[0][0]

    @discord.ui.button(style=discord.ButtonStyle.green, custom_id="btn_a")
    async def a(self, interaction: discord.Interaction, button: discord.ui.Button):
        bal = await self.onboarding(interaction)
        await interaction.response.send_modal(BetModal(button.label, bal))

    @discord.ui.button(style=discord.ButtonStyle.red, custom_id="btn_b")
    async def b(self, interaction: discord.Interaction, button: discord.ui.Button):
        bal = await self.onboarding(interaction)
        await interaction.response.send_modal(BetModal(button.label, bal))

# --- BOT ENGINE ---
class MarketBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())

    async def setup_hook(self):
        init_db()
        self.add_view(BetView()) # Keeps buttons working after restart
        self.market_loop.start()
        await self.tree.sync() # Makes Slash Commands show up instantly

    @tasks.loop(minutes=1)
    async def market_loop(self):
        now = datetime.datetime.now(EST)
        today = datetime.date.today().isoformat()

        # 9:40 AM Fail-safe
        if now.hour == 9 and now.minute == 40:
            if not db_query("SELECT * FROM history WHERE date = ?", (today,), fetch=True):
                await self.post_auto_bet()

        # 5:30 PM Automatic Close & Notification
        if now.hour == 17 and now.minute == 30:
            chan = self.get_channel(CHANNEL_ID)
            await chan.send("🔒 **MARKET CLOSED.** No more bets for today. Processing results soon...")

    async def post_auto_bet(self):
        feed = feedparser.parse("https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en")
        headline = feed.entries[0].title if feed.entries else "Will the market end green?"
        question = f"AUTO-BET: {headline}"
        db_query("INSERT INTO history VALUES (?, ?, 'PENDING')", (datetime.date.today().isoformat(), question))
        chan = self.get_channel(CHANNEL_ID)
        await chan.send(embed=discord.Embed(title="🌍 Daily Market Open", description=question, color=0x3498db), view=BetView("Yes", "No"))

bot = MarketBot()

@bot.tree.command(name="leaderboard", description="View the top 10 richest players")
async def leaderboard(interaction: discord.Interaction):
    data = db_query("SELECT user_id, balance FROM users ORDER BY balance DESC LIMIT 10", fetch=True)
    embed = discord.Embed(title="🏆 MARKET LEADERBOARD", color=0xFFD700)
    for i, (uid, bal) in enumerate(data, 1):
        member = interaction.guild.get_member(uid)
        name = member.display_name if member else f"User {uid}"
        embed.add_field(name=f"{i}. {name}", value=f"${bal}", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="create_bet", description="Admin: Create a bet with custom button labels")
@app_commands.checks.has_permissions(administrator=True)
async def create_bet(interaction: discord.Interaction, question: str, answer_a: str = "Yes", answer_b: str = "No"):
    today = datetime.date.today().isoformat()
    db_query("INSERT OR REPLACE INTO history VALUES (?, ?, 'PENDING')", (today, question))
    
    view = BetView(label_a=answer_a, label_b=answer_b)
    embed = discord.Embed(title="⚖️ POLITICAL MARKET OPEN", description=f"**{question}**", color=0x2ecc71)
    embed.add_field(name="Option A", value=answer_a, inline=True)
    embed.add_field(name="Option B", value=answer_b, inline=True)
    embed.set_footer(text="Market closes at 5:30 PM EST")
    
    await interaction.response.send_message(embed=embed, view=view)

keep_alive()
bot.run(os.environ.get('TOKEN'))


