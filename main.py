import discord
from discord.ext import tasks, commands
from discord import app_commands
import sqlite3, datetime, zoneinfo, random, feedparser, os

# --- CONFIG ---
TOKEN = os.getenv('TOKEN')
CHANNEL_ID = 1468975504899178576 # Replace with your Channel ID
GUILD_ID = 1140664003371212830   # Replace with your Server ID
EST = zoneinfo.ZoneInfo("America/New_York")
STARTING_CASH = 500

ROLES = {0: "In the Hunt", 1000: "Casual Bettor", 2500: "Novice Better", 
         5000: "Keeper of Coin", 7500: "Hail to the King", 10000: "The fucking Best"}

# --- DB LOGIC ---
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

# --- UI (MODALS & VIEWS) ---
class BetModal(discord.ui.Modal, title='Place Your Wager'):
    wager = discord.ui.TextInput(label='Amount', placeholder='e.g. 100')
    def __init__(self, choice, balance):
        super().__init__()
        self.choice, self.balance = choice, balance

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amt = int(self.wager.value)
            if amt > self.balance or amt <= 0: raise ValueError
        except:
            return await interaction.response.send_message(f"❌ Invalid amount!", ephemeral=True)
        db_query("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amt, interaction.user.id))
        db_query("INSERT INTO bets VALUES (?, ?, ?, ?)", (interaction.user.id, amt, self.choice, datetime.date.today().isoformat()))
        await interaction.response.send_message(f"✅ ${amt} wagered on {self.choice}!", ephemeral=True)

class BetView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="Option A", style=discord.ButtonStyle.green, custom_id="a")
    async def a(self, interaction: discord.Interaction, button: discord.ui.Button):
        bal = await self.onboarding(interaction)
        await interaction.response.send_modal(BetModal("A", bal))
    @discord.ui.button(label="Option B", style=discord.ButtonStyle.red, custom_id="b")
    async def b(self, interaction: discord.Interaction, button: discord.ui.Button):
        bal = await self.onboarding(interaction)
        await interaction.response.send_modal(BetModal("B", bal))

    async def onboarding(self, interaction):
        res = db_query("SELECT balance FROM users WHERE user_id = ?", (interaction.user.id,), fetch=True)
        if not res:
            db_query("INSERT INTO users VALUES (?, ?)", (interaction.user.id, STARTING_CASH))
            role = discord.utils.get(interaction.guild.roles, name="In the Hunt")
            if role: await interaction.user.add_roles(role)
            return STARTING_CASH
        return res[0][0]

# --- THE BOT ENGINE ---
class MarketBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())
    async def setup_hook(self):
        init_db()
        self.add_view(BetView())
        self.market_loop.start()
        await self.tree.sync() # Syncs slash commands on startup

    @tasks.loop(minutes=1)
    async def market_loop(self):
        now = datetime.datetime.now(EST)
        if now.hour == 9 and now.minute == 40:
            if not db_query("SELECT * FROM history WHERE date = ?", (datetime.date.today().isoformat(),), fetch=True):
                await self.post_auto_bet()
        if now.hour == 17 and now.minute == 30:
            await self.resolve_day()

    async def post_auto_bet(self):
        feed = feedparser.parse("https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en")
        headline = feed.entries[0].title if feed.entries else "Will the market stay green?"
        db_query("INSERT INTO history VALUES (?, ?, 'PENDING')", (datetime.date.today().isoformat(), headline))
        chan = self.get_channel(CHANNEL_ID)
        await chan.send(embed=discord.Embed(title="🌍 Market Open", description=headline, color=0x3498db), view=BetView())

    async def resolve_day(self):
        winner = random.choice(["A", "B"])
        today = datetime.date.today().isoformat()
        winners = db_query("SELECT user_id, amount FROM bets WHERE date = ? AND choice = ?", (today, winner), fetch=True)
        for uid, amt in winners:
            db_query("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amt * 2, uid))
            res = db_query("SELECT balance FROM users WHERE user_id = ?", (uid,), fetch=True)
            await self.update_roles(uid, res[0][0])
        chan = self.get_channel(CHANNEL_ID)
        await chan.send(f"🏁 **MARKET RESOLVED.** Winner: Side {winner}!")

    async def update_roles(self, user_id, balance):
        guild = self.get_guild(GUILD_ID)
        if not guild: return
        member = guild.get_member(user_id)
        if not member: return
        new_role_name = "In the Hunt"
        for thresh, name in sorted(ROLES.items()):
            if balance >= thresh: new_role_name = name
        role = discord.utils.get(guild.roles, name=new_role_name)
        if role and role not in member.roles:
            all_r = [discord.utils.get(guild.roles, name=n) for n in ROLES.values()]
            await member.remove_roles(*[r for r in all_r if r and r in member.roles])
            await member.add_roles(role)

bot = MarketBot()

@bot.tree.command(name="leaderboard")
async def leaderboard(interaction: discord.Interaction):
    data = db_query("SELECT user_id, balance FROM users ORDER BY balance DESC LIMIT 10", fetch=True)
    embed = discord.Embed(title="🏆 Top 10 Bettors", color=0xFFD700)
    for i, (uid, bal) in enumerate(data, 1):
        member = interaction.guild.get_member(uid)
        name = member.display_name if member else f"User {uid}"
        embed.add_field(name=f"{i}. {name}", value=f"${bal}", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="create_bet")
@app_commands.checks.has_permissions(administrator=True)
async def create_bet(interaction: discord.Interaction, question: str):
    db_query("INSERT OR REPLACE INTO history VALUES (?, ?, 'PENDING')", (datetime.date.today().isoformat(), question))
    await interaction.response.send_message(embed=discord.Embed(title="🎰 CUSTOM BET", description=question, color=0x2ecc71), view=BetView())


bot.run(TOKEN)
