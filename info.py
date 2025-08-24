import json
import os
from rapidfuzz import process
import discord
from discord.ext import commands
from dotenv import load_dotenv
import re
import asyncio
import random
from datetime import datetime
import sqlite3

TIMEZONE_OFFSET = 2  # Hogwarts time (CEST)

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))
REPLY_CHANNEL_ID = int(os.getenv("DISCORD_REPLY_CHANNEL_ID"))
OWNER_ID = int(os.getenv("OWNER_ID"))

# Load tips.json
with open("tips.json") as f:
    tips = json.load(f)
    for event, data in tips.items():
        if isinstance(data.get("tips"), str):
            data["tips"] = data["tips"].strip().split("\n")
        elif isinstance(data.get("tips"), list):
            cleaned = []
            for tip in data["tips"]:
                if isinstance(tip, str):
                    cleaned.append(tip.replace('\r', '').strip())
                elif isinstance(tip, dict):
                    cleaned_tip = {}
                    for k, v in tip.items():
                        cleaned_tip[k] = v.replace('\r', '').strip() if isinstance(v, str) else v
                    cleaned.append(cleaned_tip)
                else:
                    cleaned.append(tip)
            data["tips"] = cleaned
        if "combo_recommendations" in data:
            for strategy, combo in data["combo_recommendations"].items():
                combo["strategy"] = combo["strategy"].replace('\r', '').strip()
                if "masks" in combo:
                    if isinstance(combo["masks"], list):
                        combo["masks"] = [mask.replace('\r', '').strip() for mask in combo["masks"]]
                    else:
                        combo["masks"] = combo["masks"].replace('\r', '').strip()
                combo["remark"] = combo["remark"].replace('\r', '').strip()
        if event == "pet_race":
            for sub_event, sub_data in data.items():
                if isinstance(sub_data, dict):
                    for strategy, strategy_data in sub_data.items():
                        if isinstance(strategy_data, dict) and "Tips" in strategy_data:
                            strategy_data["Tips"] = [tip.replace('\r', '').strip() for tip in strategy_data["Tips"]]

# Load videos.json
with open("videos.json") as f:
    video_urls = json.load(f)

# Initialize SQLite for usage and suggestions
def init_db():
    conn = sqlite3.connect("bot_usage.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS usage (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, event_name TEXT, timestamp TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS suggestions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, event_name TEXT, tip_text TEXT, timestamp TEXT)''')
    conn.commit()
    conn.close()

init_db()

def get_closest_event(event_name, tips_dict, threshold=60):
    matches = process.extract(event_name, tips_dict.keys(), limit=1)
    if matches and matches[0][1] >= threshold:
        return matches[0][0]
    return None

def prioritize_tips(tips):
    # Score tips based on keywords and brevity
    def score_tip(tip):
        score = 0
        text = tip['details'] if isinstance(tip, dict) else tip
        keywords = ["priority", "prioritize", "key", "focus", "essential", "critical"]
        for kw in keywords:
            if kw.lower() in text.lower():
                score += 10
        score -= len(text) // 50  # Prefer shorter tips
        return score
    
    if isinstance(tips, str):
        tips = tips.split("\n")
    scored_tips = [(tip, score_tip(tip)) for tip in tips]
    scored_tips.sort(key=lambda x: x[1], reverse=True)
    return [tip[0] for tip in scored_tips[:2]]  # Top 2 tips

def format_event_response(event_name, event_data, include_video=False, user_id=None):
    # Log usage
    conn = sqlite3.connect("bot_usage.db")
    c = conn.cursor()
    c.execute("INSERT INTO usage (user_id, event_name, timestamp) VALUES (?, ?, ?)",
              (user_id, event_name, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()
    
    # Create Discord embed
    embed = discord.Embed(
        title=f"{event_name.title()}",
        description="You dare disturb my brewing for such trivialities? Heed this wisdom or face oblivion.",
        color=0x1A3C34  # Slytherin green
    )
    embed.set_footer(text="Severus Snape, Potions Master")
    
    # General strategies
    general_plans = {
        "masquerade ball": "Concoct a mask blend (2-3 purples, 1-2 golds) and test in practice mode to avoid humiliating defeat.",
        "realm_revival": "Unite with your alliance, save stamina for high-value targets, and deploy double dice with precision.",
        "nibelungen treasure": "Mine tiles efficiently, target Dwarf Kings, and use gold buffs only when victory is assured.",
        "pet race": "Select a walking or running strategy as if brewing Polyjuice; pace attempts to outwit inferiors.",
        "school of athens": "Build Debate Score daily, join a team, and save stamina for Level 3 ascension, lest you fail spectacularly.",
        "mystery murder": "Prioritize keys over futile combat, use clues for efficient tiles, and avoid wasting my time."
    }
    
    embed.add_field(
        name="⚗️ Elixir of Victory",
        value=general_plans.get(event_name.lower(), "No strategy for such incompetence."),
        inline=False
    )
    
    # Prioritize tips
    if "tips" in event_data:
        tips = prioritize_tips(event_data["tips"])
        if event_name.lower() == "mystery murder":
            tips_text = "\n".join(f"• **{tip['title']}**: {tip['details'][:80]}" for tip in tips if isinstance(tip, dict))
        else:
            tips_text = "\n".join(f"• {tip[:80]}" for tip in tips if isinstance(tip, str))
        embed.add_field(name="🧪 Key Ingredients", value=tips_text or "No wisdom for the witless.", inline=False)
    
    # Strategy
    if "combo_recommendations" in event_data:
        combo = list(event_data["combo_recommendations"].values())[0]
        strategy_text = f"**{combo['strategy']}**: {', '.join(combo.get('masks', [])) or combo.get('remark', 'N/A')}"
        embed.add_field(name="🧪 Brewed Tactic", value=strategy_text[:200], inline=False)
    
    # Event-specific notes
    if event_name.lower() == "pet race":
        embed.add_field(name="📜 Note", value="🐇🐢 Choose your strategy with care. Consult peak records for optimal skill blends.", inline=False)
    elif event_name.lower() == "school of athens":
        embed.add_field(
            name="📜 Critical Insights",
            value=f"• Objective: {event_data.get('Goal', 'N/A')}\n• Max Level: {event_data.get('MaxLevel', 'N/A')}\n• Teamwork: Essential, or face my scorn.",
            inline=False
        )
    
    # Video embed
    if include_video:
        video_url = video_urls.get(event_name.lower())
        if video_url and re.match(r"https?://(www\.)?youtube\.com/watch\?v=[\w-]+", video_url):
            embed.add_field(name="📽️ Visual Elixir", value=f"[Watch this guide]({video_url})", inline=False)
        else:
            embed.add_field(name="📽️ Visual Elixir", value="No worthy guide exists for your incompetence.", inline=False)
    
    return embed

def snape_no_match():
    return discord.Embed(
        title="Utter Incompetence",
        description="You dare waste my time with such a poorly worded request? Spell the event correctly, or face my displeasure.",
        color=0x1A3C34
    )

def tos_embed():
    embed = discord.Embed(
        title="Rules of the Potions Master",
        description="You will obey these decrees, or face my wrath. My time is not to be squandered by fools.",
        color=0x1A3C34
    )
    embed.add_field(
        name="🧪 Usage Guidelines",
        value="• Use `!tip <event>` in the designated channel only.\n• Include 'video' for YouTube guides (e.g., `!tip Pet Race video`).\n• Do not spam commands, lest you scrub cauldrons for eternity.",
        inline=False
    )
    embed.add_field(
        name="📜 Server Harmony",
        value="• Respect alliance decisions, especially in cross-server events.\n• Submit tips via `!suggest` to aid your peers, not to waste my time.",
        inline=False
    )
    embed.add_field(
        name="⚗️ Conduct",
        value="• No disruptive behavior. My patience is thinner than a poorly brewed potion.\n• Contact the owner via DM for issues, not in public channels.",
        inline=False
    )
    embed.set_footer(text="Severus Snape, Potions Master")
    return embed

def review_suggestions_embed(page=1):
    conn = sqlite3.connect("bot_usage.db")
    c = conn.cursor()
    c.execute("SELECT id, user_id, event_name, tip_text, timestamp FROM suggestions ORDER BY timestamp DESC")
    suggestions = c.fetchall()
    conn.close()
    
    if not suggestions:
        return discord.Embed(
            title="No Suggestions",
            description="The masses have failed to contribute anything worthwhile. Pathetic.",
            color=0x1A3C34
        )
    
    items_per_page = 5
    total_pages = (len(suggestions) + items_per_page - 1) // items_per_page
    page = max(1, min(page, total_pages))
    start_idx = (page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    page_suggestions = suggestions[start_idx:end_idx]
    
    embed = discord.Embed(
        title="Submitted Suggestions",
        description=f"These are the pitiful suggestions submitted by the masses. Page {page}/{total_pages}.",
        color=0x1A3C34
    )
    for idx, suggestion in enumerate(page_suggestions, start=start_idx + 1):
        suggestion_id, user_id, event_name, tip_text, timestamp = suggestion
        embed.add_field(
            name=f"Suggestion #{suggestion_id}",
            value=f"**User ID**: {user_id}\n**Event**: {event_name.title()}\n**Tip**: {tip_text[:150]}{'...' if len(tip_text) > 150 else ''}\n**Time**: {timestamp}",
            inline=False
        )
    
    embed.set_footer(text=f"Severus Snape, Potions Master | Use '!review_suggestions <page>' for more")
    return embed

async def send_embed(ctx, embed):
    await ctx.send(embed=embed)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.dm_messages = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}, ready to brew chaos.")
    bot.loop.create_task(status_loop())

@bot.command(name="tip")
async def tip(ctx, *, event_name: str):
    print(f"Processing !tip for {event_name} from {ctx.author} at {ctx.channel.id}")
    if ctx.channel.id != CHANNEL_ID:
        embed = discord.Embed(
            title="Misplaced Request",
            description="Do not test my patience by using this command outside the designated channel.",
            color=0x1A3C34
        )
        await ctx.send(embed=embed)
        return
    embed = respond_to_event(event_name, ctx.author.id)
    await send_embed(ctx, embed)

@bot.command(name="tos")
async def tos(ctx):
    print(f"Processing !tos from {ctx.author} at {ctx.channel.id}")
    if ctx.channel.id != CHANNEL_ID:
        embed = discord.Embed(
            title="Misplaced Request",
            description="Do not test my patience by using this command outside the designated channel.",
            color=0x1A3C34
        )
        await ctx.send(embed=embed)
        return
    embed = tos_embed()
    await send_embed(ctx, embed)

@bot.command(name="suggest")
async def suggest(ctx, *, suggestion: str):
    print(f"Processing !suggest for '{suggestion}' from {ctx.author} at {ctx.channel.id}")
    if ctx.channel.id != CHANNEL_ID:
        embed = discord.Embed(
            title="Misplaced Request",
            description="Do not test my patience by using this command outside the designated channel.",
            color=0x1A3C34
        )
        await ctx.send(embed=embed)
        return
    # Parse suggestion: expect format like "Masquerade Ball Use Parrot mask"
    parts = suggestion.split(" ", 1)
    if len(parts) < 2:
        embed = discord.Embed(
            title="Invalid Suggestion",
            description="Format: `!suggest <event> <tip>`. Don’t waste my time with incompetence.",
            color=0x1A3C34
        )
        await ctx.send(embed=embed)
        return
    event_name, tip_text = parts
    matched_event = get_closest_event(event_name, tips)
    if not matched_event:
        embed = discord.Embed(
            title="Invalid Event",
            description="No such event exists. Spell it correctly, you fool.",
            color=0x1A3C34
        )
        await ctx.send(embed=embed)
        return
    # Store suggestion in SQLite
    conn = sqlite3.connect("bot_usage.db")
    c = conn.cursor()
    c.execute("INSERT INTO suggestions (user_id, event_name, tip_text, timestamp) VALUES (?, ?, ?, ?)",
              (ctx.author.id, matched_event, tip_text[:500], datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()
    # Notify owner
    owner = await bot.fetch_user(OWNER_ID)
    embed_owner = discord.Embed(
        title="New Suggestion",
        description=f"From **{ctx.author}** (ID: {ctx.author.id}):\n**Event**: {matched_event.title()}\n**Tip**: {tip_text[:500]}",
        color=0x1A3C34
    )
    await owner.send(embed=embed_owner)
    # Confirm with user
    embed = discord.Embed(
        title="Suggestion Received",
        description=f"Your suggestion for **{matched_event.title()}** has been noted: '{tip_text[:100]}...'. It will be reviewed, assuming it’s not utterly useless.",
        color=0x1A3C34
    )
    await ctx.send(embed=embed)

@bot.command(name="review_suggestions")
async def review_suggestions(ctx, page: int = 1):
    print(f"Processing !review_suggestions for page {page} from {ctx.author} at {ctx.channel.id}")
    if ctx.author.id != OWNER_ID:
        embed = discord.Embed(
            title="Unauthorized",
            description="Only the Potions Master’s chosen may review suggestions. Begone, imposter.",
            color=0x1A3C34
        )
        await ctx.send(embed=embed)
        return
    if not isinstance(ctx.channel, discord.DMChannel) and ctx.channel.id != REPLY_CHANNEL_ID:
        embed = discord.Embed(
            title="Misplaced Request",
            description="Use this command in DMs or the reply channel, you incompetent fool.",
            color=0x1A3C34
        )
        await ctx.send(embed=embed)
        return
    embed = review_suggestions_embed(page)
    await send_embed(ctx, embed)

@bot.command(name="reply")
@commands.has_permissions(administrator=True)
async def reply(ctx, *, message: str):
    print(f"Processing !reply from {ctx.author} at {ctx.channel.id}")
    if ctx.channel.id != REPLY_CHANNEL_ID:
        embed = discord.Embed(
            title="Forbidden Action",
            description="The !reply command is restricted to the reply channel, you imbecile.",
            color=0x1A3C34
        )
        await ctx.send(embed=embed)
        return
    reply_channel = bot.get_channel(REPLY_CHANNEL_ID)
    if not reply_channel:
        embed = discord.Embed(
            title="Configuration Error",
            description="The reply channel is misconfigured. Inform your incompetent administrator.",
            color=0x1A3C34
        )
        await ctx.send(embed=embed)
        return
    try:
        await ctx.message.delete()
    except discord.errors.Forbidden:
        embed = discord.Embed(
            title="Permission Denied",
            description="I lack the power to erase your foolishness from this channel.",
            color=0x1A3C34
        )
        await ctx.send(embed=embed)
        return
    await reply_channel.send(message)

@reply.error
async def reply_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        embed = discord.Embed(
            title="Unauthorized",
            description="Only those with administrative prowess may wield the !reply command.",
            color=0x1A3C34
        )
    else:
        embed = discord.Embed(
            title="Error",
            description="An error has occurred, as if you needed more proof of your inadequacy.",
            color=0x1A3C34
        )
    await ctx.send(embed=embed)

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if message.guild is None:
        if message.author.id != OWNER_ID:
            owner = await bot.fetch_user(OWNER_ID)
            embed = discord.Embed(
                title="Incoming Missive",
                description=f"From **{message.author}** (ID: {message.author.id}):\n{message.content}",
                color=0x1A3C34
            )
            await owner.send(embed=embed)
            return
        if message.author.id == OWNER_ID:
            if message.content.startswith("reply"):
                parts = message.content.split(" ", 2)
                if len(parts) < 3:
                    embed = discord.Embed(
                        title="Incorrect Usage",
                        description="Usage: reply <USER_ID> <message>, you fool.",
                        color=0x1A3C34
                    )
                    await message.channel.send(embed=embed)
                    return
                try:
                    user_id = int(parts[1])
                except ValueError:
                    embed = discord.Embed(
                        title="Invalid ID",
                        description="Invalid USER_ID. Numbers, not nonsense.",
                        color=0x1A3C34
                    )
                    await message.channel.send(embed=embed)
                    return
                user_message = parts[2]
                try:
                    user = await bot.fetch_user(user_id)
                    await user.send(user_message)
                    embed = discord.Embed(
                        title="Message Sent",
                        description=f"✅ Dispatched to {user} (ID: {user_id})",
                        color=0x1A3C34
                    )
                    await message.channel.send(embed=embed)
                except Exception as e:
                    embed = discord.Embed(
                        title="Delivery Failed",
                        description=f"❌ Failed to send: {e}",
                        color=0x1A3C34
                    )
                    await message.channel.send(embed=embed)
            return
    await bot.process_commands(message)

async def status_loop():
    day_statuses = [
        "🧪 Brewing a flawless Draught of Peace",
        "📜 Grading your abysmal essays",
        "🖤 Sneering at Gryffindor antics",
        "⚗️ Perfecting my latest potion"
    ]
    night_statuses = [
        "🌙 Patrolling the dungeons for miscreants",
        "🕯️ Contemplating the Dark Arts",
        "💤 Resting, but never for long"
    ]
    while True:
        hour_utc = datetime.utcnow().hour
        local_hour = (hour_utc + TIMEZONE_OFFSET) % 24
        status_message = random.choice(day_statuses if 6 <= local_hour < 22 else night_statuses)
        activity = discord.Game(status_message)
        await bot.change_presence(activity=activity)
        await asyncio.sleep(7200)  # Update every 2 hours

def respond_to_event(user_input, user_id):
    event_name = user_input.strip().lower()
    include_video = "video" in event_name.lower()
    event_name = event_name.replace("video", "").strip()
    matched_event = get_closest_event(event_name, tips)
    if matched_event:
        return format_event_response(matched_event, tips[matched_event], include_video, user_id)
    return snape_no_match()

bot.run(TOKEN)