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
            cleaned = []
            for tip in data["tips"]:
                # If it’s a plain string tip
                if isinstance(tip, str):
                    cleaned.append(tip.replace('\r', '').strip())

                # If it’s a dict tip with title / details (or anything else)
                elif isinstance(tip, dict):
                    cleaned_tip = {}
                    for k, v in tip.items():
                        cleaned_tip[k] = (
                            v.replace('\r', '').strip()
                            if isinstance(v, str) else v
                        )
                    cleaned.append(cleaned_tip)

                # Fallback – just append untouched
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

def get_closest_event(event_name, tips_dict, threshold=60):
    matches = process.extract(event_name, tips_dict.keys(), limit=1)
    if matches:
        match_name, score, _ = matches[0]
        if score >= threshold:
            return match_name
    return None

def format_event_response(event_name, event_data):
    reply = f"You seek knowledge on **{event_name.title()}**... How predictably desperate.\n"

    # Handle simple tips
    if "tips" in event_data:
        tips = event_data["tips"]
        if isinstance(tips, list):
            tips_formatted = "\n".join(f"- {tip}" for tip in tips)
        else:
            tips_formatted = f"- {tips}"
        reply += f"\n**Tips:**\n{tips_formatted}\n"
    else:
        reply += "\n**Tips:**\nNo tips available.\n"

    # Handle combo recommendations
    if "combo_recommendations" in event_data:
        combos = event_data["combo_recommendations"]
        combos_formatted = "\n".join(f"- {combo}" for combo in combos)
        reply += f"\n**Combo Recommendations:**\n{combos_formatted}\n"

    # Handle pet race
    if event_name.lower() == "pet race":
        reply += (
            "\n**Note:** 🐇🐢 For the Pet Race, stamina management is critical. "
            "Focus on synergy and timing for your best pets."
        )

    # Handle School of Athens
    if event_name.lower() == "school of athens":
        reply += "\n**📜 School of Athens Event Details:**\n"

        # Basic goal and level
        reply += f"- Goal: {event_data.get('Goal', 'N/A')}\n"
        reply += f"- Max Level: {event_data.get('MaxLevel', 'N/A')}\n"

        # Level 3 details
        level3 = event_data.get("Level3", {})
        if level3:
            reply += "**Level 3 Details:**\n"
            for k, v in level3.items():
                reply += f"  - {k}: {v}\n"

        # Teams
        teams = event_data.get("Teams", {})
        if teams:
            reply += "\n**Teams:**\n"
            for k, v in teams.items():
                if isinstance(v, list):
                    reply += f"- {k}:\n"
                    for item in v:
                        reply += f"  - {item}\n"
                else:
                    reply += f"- {k}: {v}\n"

        # DebateScore
        debate_score = event_data.get("DebateScore", {})
        if debate_score:
            reply += "\n**Debate Score:**\n"
            for k, v in debate_score.items():
                reply += f"- {k}: {v}\n"

        # DebatingHalls
        debating_halls = event_data.get("DebatingHalls", {})
        if debating_halls:
            reply += "\n**Debating Halls:**\n"
            for k, v in debating_halls.items():
                reply += f"- {k}: {v}\n"

        # BattleMechanics PointsTable
        battle_mech = event_data.get("BattleMechanics", {})
        if battle_mech:
            reply += "\n**Battle Mechanics:**\n"
            for k, v in battle_mech.items():
                if k != "PointsTable":
                    if isinstance(v, dict):
                        reply += f"- {k}:\n"
                        for sub_k, sub_v in v.items():
                            reply += f"  - {sub_k}: {sub_v}\n"
                    else:
                        reply += f"- {k}: {v}\n"

            # PointsTable formatting
            points_table = battle_mech.get("PointsTable", [])
            if points_table:
                reply += "\n**Points Table:**\n"
                for entry in points_table:
                    line = ", ".join(f"{k}: {v}" for k, v in entry.items())
                    reply += f"- {line}\n"

        # MarkingSystem
        marking_system = event_data.get("MarkingSystem", {})
        if marking_system:
            reply += "\n**Marking System:**\n"
            for k, v in marking_system.items():
                if isinstance(v, list):
                    reply += f"- {k}:\n"
                    for item in v:
                        reply += f"  - {item}\n"
                elif isinstance(v, dict):
                    reply += f"- {k}:\n"
                    for sub_k, sub_v in v.items():
                        reply += f"  - {sub_k}: {sub_v}\n"
                else:
                    reply += f"- {k}: {v}\n"

        # Stamina
        stamina = event_data.get("Stamina", {})
        if stamina:
            reply += "\n**Stamina:**\n"
            for k, v in stamina.items():
                reply += f"- {k}: {v}\n"

        # Ascension
        ascension = event_data.get("Ascension", {})
        if ascension:
            reply += "\n**Ascension:**\n"
            for k, v in ascension.items():
                if isinstance(v, dict):
                    reply += f"- {k}:\n"
                    for sub_k, sub_v in v.items():
                        reply += f"  - {sub_k}: {sub_v}\n"
                else:
                    reply += f"- {k}: {v}\n"

        # Certificates
        certs = event_data.get("Certificates", {})
        if certs:
            reply += "\n**Certificates:**\n"
            for k, v in certs.items():
                if isinstance(v, list):
                    reply += f"- {k}:\n"
                    for item in v:
                        reply += f"  - {item}\n"
                else:
                    reply += f"- {k}: {v}\n"

        # EventScrolls
        scrolls = event_data.get("EventScrolls", {})
        if scrolls:
            reply += "\n**Event Scrolls:**\n"
            for k, v in scrolls.items():
                if isinstance(v, list):
                    reply += f"- {k}:\n"
                    for item in v:
                        if isinstance(item, dict):
                            sub_line = ", ".join(f"{ik}: {iv}" for ik, iv in item.items())
                            reply += f"  - {sub_line}\n"
                        else:
                            reply += f"  - {item}\n"
                else:
                    reply += f"- {k}: {v}\n"

        # AthenianWisdomCurrency
        awc = event_data.get("AthenianWisdomCurrency", {})
        if awc:
            reply += "\n**Athenian Wisdom Currency:**\n"
            for k, v in awc.items():
                if isinstance(v, list):
                    reply += f"- {k}:\n"
                    for item in v:
                        reply += f"  - {item}\n"
                else:
                    reply += f"- {k}: {v}\n"
        
        # Handle Mystery Murder event
    if event_name.lower() == "mystery murder":
        # Add description
        description = event_data.get("description", "No description available.")
        reply += f"\n**Description:**\n{description}\n"

        # Add note if present
        note = event_data.get("note")
        if note:
            reply += f"\n**Note:**\n{note}\n"

    reply += "\nDo try not to waste this information..."
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
