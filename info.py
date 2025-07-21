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

TIMEZONE_OFFSET = 2  # adjust to match your Hogwarts time if needed

# Load environment variables from .env
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))
REPLY_CHANNEL_ID = int(os.getenv("DISCORD_REPLY_CHANNEL_ID"))
OWNER_ID = int(os.getenv("OWNER_ID")) 

# Load and sanitize tips JSON
with open("tips.json") as f:
    tips = json.load(f)
    for event, data in tips.items():
        if isinstance(data.get("tips"), str):
            data["tips"] = data["tips"].strip()
        elif isinstance(data.get("tips"), list):
            data["tips"] = [tip.replace('\r', '').strip() for tip in data["tips"]]
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

def get_closest_event(event_name, tips_dict, threshold=60):
    matches = process.extract(event_name, tips_dict.keys(), limit=1)
    if matches:
        match_name, score, _ = matches[0]
        if score >= threshold:
            return match_name
    return None

def format_event_response(event_name, event_data):
    reply = f"You seek knowledge on **{event_name.title()}**... How predictably desperate.\nVery well, here is what you require:\n\n"
    if isinstance(event_data.get("tips"), str):
        reply += "**Tips:**\n" + event_data["tips"] + "\n"
    elif isinstance(event_data.get("tips"), list):
        reply += "**Tips:**\n"
        for idx, tip in enumerate(event_data["tips"], 1):
            reply += f"{idx}. {tip}\n"
    else:
        reply += "**Tips:**\nNo tips available.\n"
    combos = event_data.get("combo_recommendations", {})
    if combos:
        reply += "\n**Combo Recommendations:**\n"
        for strategy, combo in combos.items():
            reply += f"- **{combo['strategy']}**\n"
            if "masks" in combo:
                if isinstance(combo.get("masks"), list):
                    masks = ", ".join(combo["masks"])
                else:
                    masks = combo["masks"]
                reply += f"  - Masks: {masks}\n"
            reply += f"  - Remark: {combo['remark']}\n"
    if event_name.lower() == "pet_race":
        reply += "\n**Pet Race Strategies:**\n"
        for sub_event, sub_data in event_data.items():
            if isinstance(sub_data, dict):
                for strategy, strategy_data in sub_data.items():
                    if isinstance(strategy_data, dict):
                        reply += f"- **{strategy}**\n"
                        if "Skills" in strategy_data:
                            reply += f"  - Skills: {', '.join(strategy_data['Skills'])}\n"
                        if "RecommendedSkills" in strategy_data:
                            reply += f"  - Recommended Skills: {', '.join(strategy_data['RecommendedSkills'])}\n"
                        if "Tips" in strategy_data:
                            reply += "  - Tips:\n"
                            for idx, tip in enumerate(strategy_data["Tips"], 1):
                                reply += f"    {idx}. {tip}\n"
    reply += "\nDo try not to waste this information, as you so often waste opportunities."
    print("Response to send:", repr(reply))
    return reply

def mcgonagall_style_no_match():
    return ("I find it astonishing that you managed to spell that so poorly even a simple matching charm fails. "
            "Clarify your request before wasting more of my time.")

def respond_to_event(user_input):
    event_name = user_input.strip().lower()
    matched_event = get_closest_event(event_name, tips)
    if matched_event:
        event_data = tips[matched_event]
        return format_event_response(matched_event, event_data)
    else:
        return mcgonagall_style_no_match()

def sanitize_response(text):
    text = ''.join(c for c in text if c.isprintable() or c == '\n')
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

async def send_long_message(ctx, response):
    if len(response) <= 1900:
        await ctx.send(response)
        return
    chunks = []
    current_chunk = ""
    for line in response.split("\n"):
        if len(current_chunk) + len(line) + 1 > 1900:
            chunks.append(current_chunk)
            current_chunk = line + "\n"
        else:
            current_chunk += line + "\n"
    if current_chunk:
        chunks.append(current_chunk)
    for chunk in chunks:
        await ctx.send(chunk)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.dm_messages = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}!")
    bot.loop.create_task(status_loop())

@bot.command(name="tip")
async def tip(ctx, *, event_name: str):
    print(f"Processing !tip command for {event_name} from {ctx.author} at {ctx.channel.id}")
    if ctx.channel.id != CHANNEL_ID:
        await ctx.send("Kindly confine your use of this command to the designated channel, unless you wish to attract unnecessary attention.")
        return
    response = respond_to_event(event_name)
    response = sanitize_response(response)
    await send_long_message(ctx, response)

@bot.command(name="reply")
@commands.has_permissions(administrator=True)
async def reply(ctx, *, message: str):
    print(f"Processing !reply command from {ctx.author} at {ctx.channel.id}")
    if ctx.channel.id != REPLY_CHANNEL_ID:
        await ctx.send("The !reply command can only be used in the designated reply channel.")
        return
    reply_channel = bot.get_channel(REPLY_CHANNEL_ID)
    if not reply_channel:
        await ctx.send("The reply channel is not properly configured. Please contact the server administrator.")
        return
    try:
        await ctx.message.delete()
    except discord.errors.Forbidden:
        await ctx.send("I lack permission to delete messages in this channel.")
        return
    await reply_channel.send(f"{message}")

@reply.error
async def reply_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You must be an administrator to use the !reply command.")
    else:
        await ctx.send("An error occurred while processing the !reply command.")

# === DM RELAYING LOGIC ===
@bot.event
async def on_message(message):
    if message.author.bot:
        return
     #=== DM Handling ===
    if message.guild is None:
        if message.author.id != OWNER_ID:
            owner = await bot.fetch_user(OWNER_ID)
            await owner.send(f"📨 New DM from **{message.author}** (ID: {message.author.id}):\n{message.content}")
            return

        # Owner sent a DM to the bot - parse reply command
        if message.author.id == OWNER_ID:
            if message.content.startswith("reply"):
                parts = message.content.split(" ", 2)
                if len(parts) < 3:
                    await message.channel.send("Usage: reply <USER_ID> <message>")
                    return
                try:
                    user_id = int(parts[1])
                except ValueError:
                    await message.channel.send("Invalid USER_ID. It must be an integer.")
                    return
                user_message = parts[2]
                try:
                    user = await bot.fetch_user(user_id)
                    await user.send(user_message)
                    await message.channel.send(f"✅ Message sent to {user} (ID: {user_id})")
                except Exception as e:
                    await message.channel.send(f"❌ Failed to send message: {e}")
            return
    await bot.process_commands(message)
    
    
async def status_loop():
    day_statuses = [
        "🪄 Brewing potions in the dungeon",
        "📚 Reading Advanced Potion-Making",
        "🧪 Teaching Potions class",
        "🖤 Staring disapprovingly"
    ]

    night_statuses = [
        "🌙 Wandering Hogwarts corridors",
        "💤 Resting in the dungeon quarters",
        "🕯️ Watching the stars silently"
    ]

    while True:
        hour_utc = datetime.utcnow().hour
        local_hour = (hour_utc + TIMEZONE_OFFSET) % 24

        if 6 <= local_hour < 22:
            status_message = random.choice(day_statuses)
        else:
            status_message = random.choice(night_statuses)

        activity = discord.Game(status_message)
        await bot.change_presence(activity=activity)

        await asyncio.sleep(7200)  # update every 2 hours

bot.run(TOKEN)
