import json
import os
from rapidfuzz import process
import discord
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))

# Load tips JSON once
with open("tips.json") as f:
    tips = json.load(f)

def get_closest_event(event_name, tips_dict, threshold=60):
    matches = process.extract(event_name, tips_dict.keys(), limit=1)
    if matches:
        match_name, score, _ = matches[0]
        if score >= threshold:
            return match_name
    return None

def format_event_response(event_name, event_data):
    reply = f"Ah, I see you seek advice on **{event_name.title()}**. Very well, here are some valuable insights:\n\n"
    reply += "**Tips:**\n"
    for idx, tip in enumerate(event_data.get("tips", []), 1):
        reply += f"{idx}. {tip}\n"
    combos = event_data.get("combos", [])
    if combos:
        reply += "\n**Combo Recommendations:**\n"
        for combo in combos:
            reply += f"- **{combo['name']}**\n"
            reply += f"  - Masks: {combo['masks']}\n"
            reply += f"  - Remark: {combo['remark']}\n"
    reply += "\nDo take these to heart; one must always be prepared. I trust this will serve you well."
    return reply

def mcgonagall_style_no_match():
    return ("Hmm, I’m afraid I don’t have any tips for that particular occasion. "
            "Perhaps you could clarify your request? Precision is important, after all.")

def respond_to_event(user_input):
    event_name = user_input.strip().lower()
    matched_event = get_closest_event(event_name, tips)
    if matched_event:
        event_data = tips[matched_event]
        return format_event_response(matched_event, event_data)
    else:
        return mcgonagall_style_no_match()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}!")

@bot.command(name="tip")
async def tip(ctx, *, event_name: str):
    # Optionally restrict to a specific channel
    if ctx.channel.id != CHANNEL_ID:
        await ctx.send("Please use this command in the designated channel.")
        return

    response = respond_to_event(event_name)
    if len(response) > 1900:
        response = response[:1900] + "\n\n*Message truncated due to length.*"
    await ctx.send(response)

bot.run(TOKEN)
