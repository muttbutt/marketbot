import discord
from discord.ext import commands
from discord import app_commands
import sqlite3, os
from keep_alive import keep_alive

# --- CONFIG ---
TOKEN = os.environ.get('TOKEN')
GUILD_ID = 1140664003371212830   # REPLACE with your Server ID
CHANNEL_ID = 1468975504899178576 # REPLACE with your specific Channel ID

# --- DATABASE ---
def init_db():
    conn = sqlite3.connect('market.db')
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance INTEGER)')
    conn.commit()
    conn.close()

# --- UI COMPONENTS ---
class BetModal(discord.ui.Modal, title='Place Your Wager'):
    wager = discord.ui.TextInput(label='Amount', placeholder='e.g. 100')
    def __init__(self, choice):
        super().__init__()
        self.choice = choice
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"✅ Bet of ${self.wager.value} on {self.choice} placed!", ephemeral=True)

class BetView(discord.ui.View):
    def __init__(self, label_a: str = "Yes", label_b: str = "No"):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label=label_a, style=discord.ButtonStyle.green, custom_id="btn_a"))
        self.add_item(discord.ui.Button(label=label_b, style=discord.ButtonStyle.red, custom_id="btn_b"))
        self.add_item(discord.ui.Button(label="🏦 Check Balance", style=discord.ButtonStyle.blurple, custom_id="btn_bal"))

    async def interaction_check(self, interaction: discord.Interaction):
        # Only allow button clicks in the specific channel
        if interaction.channel_id != CHANNEL_ID:
            await interaction.response.send_message("❌ Bets can only be placed in the betting channel!", ephemeral=True)
            return False
            
        cid = interaction.data['custom_id']
        if cid == "btn_bal":
            await interaction.response.send_message(f"🏦 Your Balance: $500", ephemeral=True)
        else:
            label = next(i.label for i in self.children if i.custom_id == cid)
            await interaction.response.send_modal(BetModal(label))
        return True

# --- BOT ENGINE ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    init_db()
    print("-" * 30)
    print(f"✅ {bot.user} is locked to Channel: {CHANNEL_ID}")
    
    guild = discord.Object(id=GUILD_ID)
    bot.tree.copy_global_to(guild=guild)
    await bot.tree.sync(guild=guild)
    print(f"✅ Hard Sync Complete for Server: {GUILD_ID}")
    print("-" * 30)

# --- SLASH COMMAND WITH CHANNEL LOCK ---
@bot.tree.command(name="create_bet", description="Admin: Post a bet")
@app_commands.checks.has_permissions(administrator=True)
async def create_bet(interaction: discord.Interaction, question: str, answer_a: str = "Yes", answer_b: str = "No"):
    # Security: Ensure command is only used in the designated channel
    if interaction.channel_id != CHANNEL_ID:
        return await interaction.response.send_message(f"❌ This command can only be used in <#{CHANNEL_ID}>", ephemeral=True)
        
    view = BetView(label_a=answer_a, label_b=answer_b)
    embed = discord.Embed(title="⚖️ MARKET OPEN", description=question, color=0x2ecc71)
    embed.add_field(name="Options", value=f"🟢 {answer_a}\n🔴 {answer_b}")
    await interaction.response.send_message(embed=embed, view=view)

# --- EXECUTION ---
keep_alive()
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ ERROR: TOKEN not found!")
