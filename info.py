import json
import os
from rapidfuzz import process
import discord
from discord.ext import commands
from dotenv import load_dotenv
import re

# Load environment variables from .env
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))

# Load and sanitize tips JSON
with open("tips.json") as f:
    tips = json.load(f)
    # Sanitize strings to remove unwanted control characters, preserve intended newlines
    for event, data in tips.items():
        if isinstance(data.get("tips"), str):
            data["tips"] = data["tips"].strip()  # Keep as string, remove leading/trailing whitespace
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
        # Special handling for pet_race nested structures
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
    
    # Handle tips (string or list)
    if isinstance(event_data.get("tips"), str):
        reply += "**Tips:**\n" + event_data["tips"] + "\n"
    elif isinstance(event_data.get("tips"), list):
        reply += "**Tips:**\n"
        for idx, tip in enumerate(event_data["tips"], 1):
            reply += f"{idx}. {tip}\n"
    else:
        reply += "**Tips:**\nNo tips available.\n"
    
    # Handle combo_recommendations (dictionary)
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
    
    # Handle pet_race special case
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
    
    reply += "\nDo try not to waste this information, as you so often waste opportunities.\n\n"
    
    # Add structure formatting with detailed combo_recommendations
    reply += f"**Structure of {event_name.title()}**\n\n"
    for key, value in event_data.items():
        reply += f"**{key}**\n"
        if key == "combo_recommendations":
            reply += "- Type: Dictionary\n- Content:\n"
            for sub_key, sub_value in value.items():
                reply += f"  - {sub_key}:\n"
                for inner_key, inner_value in sub_value.items():
                    if isinstance(inner_value, list):
                        inner_content = ", ".join(inner_value)
                        reply += f"    - {inner_key}: List - {inner_content}\n"
                    else:
                        reply += f"    - {inner_key}: {inner_value}\n"
        elif isinstance(value, str):
            reply += f"- Type: String\n- Content: {value}\n"
        elif isinstance(value, list):
            reply += f"- Type: List\n- Content:\n"
            for idx, item in enumerate(value, 1):
                if isinstance(item, dict):
                    reply += f"  {idx}. Dictionary with keys: {', '.join(item.keys())}\n"
                else:
                    reply += f"  {idx}. {item}\n"
        elif isinstance(value, dict):
            reply += f"- Type: Dictionary\n- Content:\n"
            for sub_key, sub_value in value.items():
                if isinstance(sub_value, dict):
                    reply += f"  - {sub_key}: Dictionary with keys: {', '.join(sub_value.keys())}\n"
                elif isinstance(sub_value, list):
                    reply += f"  - {sub_key}: List of {len(sub_value)} items\n"
                else:
                    reply += f"  - {sub_key}: {sub_value}\n"
        reply += "\n"
    
    print("Response to send:", repr(reply))  # Debug output
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
    # Preserve intended newlines, remove unwanted control characters
    text = ''.join(c for c in text if c.isprintable() or c == '\n')
    text = re.sub(r'\n{3,}', '\n\n', text)  # Collapse excessive newlines
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

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}!")

@bot.command(name="tip")
async def tip(ctx, *, event_name: str):
    print(f"Processing !tip command for {event_name} from {ctx.author} at {ctx.channel.id}")
    if ctx.channel.id != CHANNEL_ID:
        await ctx.send("Kindly confine your use of this command to the designated channel, unless you wish to attract unnecessary attention.")
        return
    response = respond_to_event(event_name)
    response = sanitize_response(response)
    await send_long_message(ctx, response)

bot.run(TOKEN)