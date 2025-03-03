import os
import datetime
import json
import requests
import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import google.generativeai as genai
from config import *

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Configure Google Gemini API
try:
    genai.configure(api_key=GEMINI_API_KEY)
except Exception as e:
    logger.critical(f"Failed to configure Gemini API: {str(e)}")
    raise SystemExit("API configuration failed. Check credentials in config.py and try again.")

# Ensure directories exist
for directory in [BASE_DIR, HISTORY_DIR, INSTRUCTION_DIR]:
    if not os.path.exists(directory):
        os.makedirs(directory)
        logger.info(f"Created directory: {directory}")

# Load system instruction from file
def load_system_instruction(username):
    """Load custom instruction from txt file for a user, return None if not found."""
    try:
        instruction_file = os.path.join(INSTRUCTION_DIR, f"{username}.txt")
        logger.info(f"Looking for instruction file: {instruction_file}")
        if os.path.exists(instruction_file):
            with open(instruction_file, 'r', encoding='utf-8') as f:
                instruction = f.read().strip()
                logger.info(f"Instruction found for {username}: {instruction}")
                if instruction:
                    return instruction
        general_file = os.path.join(INSTRUCTION_DIR, "general.txt")
        logger.info(f"Looking for general file: {general_file}")
        if os.path.exists(general_file):
            with open(general_file, 'r', encoding='utf-8') as f:
                instruction = f.read().strip()
                logger.info(f"General instruction found: {instruction}")
                if instruction:
                    return instruction
        logger.info(f"No instruction found for {username}")
        return None
    except Exception as e:
        logger.error(f"Error loading instruction for {username}: {str(e)}")
        return None

# Load user-specific instruction only (for showinstruction)
def load_user_instruction(username):
    """Load only the user-specific instruction, excluding general.txt."""
    try:
        instruction_file = os.path.join(INSTRUCTION_DIR, f"{username}.txt")
        if os.path.exists(instruction_file):
            with open(instruction_file, 'r', encoding='utf-8') as f:
                instruction = f.read().strip()
                if instruction:
                    return instruction
        return None
    except Exception as e:
        logger.error(f"Error loading user instruction for {username}: {str(e)}")
        return None

# Save custom instruction for a user
def save_system_instruction(username, instruction):
    """Save custom instruction to a file named after the username."""
    try:
        instruction_file = os.path.join(INSTRUCTION_DIR, f"{username}.txt")
        with open(instruction_file, 'w', encoding='utf-8') as f:
            f.write(instruction.strip())
        logger.info(f"Saved instruction for {username} to {instruction_file}")
        return True
    except Exception as e:
        logger.error(f"Error saving instruction for {username}: {str(e)}")
        return False

# Delete custom instruction for a user
def delete_system_instruction(username):
    """Delete the custom instruction file for a user."""
    try:
        instruction_file = os.path.join(INSTRUCTION_DIR, f"{username}.txt")
        if os.path.exists(instruction_file):
            os.remove(instruction_file)
            logger.info(f"Deleted instruction file for {username}: {instruction_file}")
            return True
        logger.info(f"No instruction file found to delete for {username}")
        return False
    except Exception as e:
        logger.error(f"Error deleting instruction for {username}: {str(e)}")
        return False

# Load or initialize chat history for a specific user
def load_history(username):
    history_file = os.path.join(HISTORY_DIR, f"{username}.json")
    try:
        if os.path.exists(history_file):
            with open(history_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    except json.JSONDecodeError:
        logger.warning(f"Corrupted history file {history_file}. Starting fresh.")
        return []
    except Exception as e:
        logger.error(f"Error loading history for {username}: {str(e)}")
        return []

def save_history(username, history):
    history_file = os.path.join(HISTORY_DIR, f"{username}.json")
    try:
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving history for {username}: {str(e)}")

def get_user_folder(username):
    now = datetime.datetime.now()
    year = now.strftime("%Y")
    month = now.strftime("%B")
    date = now.strftime("%d")
    folder_path = os.path.join(BASE_DIR, username, year, month, date)
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        logger.info(f"Created user folder: {folder_path}")
    return folder_path

def split_text_naturally(text, max_length=4096):
    """Split text into chunks at natural boundaries without breaking words, within max_length."""
    if len(text) <= max_length:
        return [text]
    
    chunks = []
    current_chunk = ""
    last_break = 0
    
    for i, char in enumerate(text):
        current_chunk += char
        
        if char.isspace() or char in "।?!,;:\n":
            last_break = i
        
        if len(current_chunk) > max_length:
            if last_break == 0:
                chunks.append(current_chunk[:max_length].strip())
                current_chunk = current_chunk[max_length:]
                last_break = 0
            else:
                chunks.append(current_chunk[:last_break + 1].strip())
                current_chunk = current_chunk[last_break + 1:].strip()
                last_break = 0
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks

async def stream_text_response(chat_id: int, content, username: str, context: ContextTypes.DEFAULT_TYPE, reply_to_message_id: int = None) -> None:
    """Stream text response chunk-by-chunk, optionally replying to the original message."""
    logger.info(f"Processing text request for chat_id {chat_id} from {username}")
    instruction = load_system_instruction(username)
    try:
        model_kwargs = {"system_instruction": instruction} if instruction else {}
        model = genai.GenerativeModel(MODEL_NAME, **model_kwargs)
    except Exception as e:
        logger.exception(f"Failed to initialize model for {username}: {str(e)}")
        await context.bot.send_message(chat_id=chat_id, text="I’m having trouble starting up. Please try again later!", reply_to_message_id=reply_to_message_id if ENABLE_MESSAGE_MENTION else None)
        return
    
    user_history = load_history(username)
    logger.info(f"Loaded history for {username}: {len(user_history)} entries")
    
    try:
        chat_session = model.start_chat(history=user_history)
    except Exception as e:
        logger.exception(f"Failed to start chat session for {username}: {str(e)}")
        await context.bot.send_message(chat_id=chat_id, text="I couldn’t start our chat. Please try again!", reply_to_message_id=reply_to_message_id if ENABLE_MESSAGE_MENTION else None)
        return
    
    current_parts = [content]
    
    message = await context.bot.send_message(chat_id=chat_id, text=TEXT_PROCESSING_MSG, reply_to_message_id=reply_to_message_id if ENABLE_MESSAGE_MENTION else None)
    message_id = message.message_id
    last_sent_text = TEXT_PROCESSING_MSG
    
    try:
        full_response = ""
        buffer = ""
        
        response = chat_session.send_message(current_parts, stream=True)
        for chunk in response:
            chunk_text = chunk.text
            if chunk_text:
                buffer += chunk_text
                
                if len(buffer) >= 100 or buffer[-1] in " ।?!,;:\n":
                    full_response += buffer
                    buffer = ""
                    
                    chunks = split_text_naturally(full_response)
                    for i, part in enumerate(chunks):
                        if i == 0 and part != last_sent_text:
                            await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=part)
                            last_sent_text = part
                        elif i > 0:
                            message = await context.bot.send_message(chat_id=chat_id, text=part, reply_to_message_id=reply_to_message_id if ENABLE_MESSAGE_MENTION else None)
                            message_id = message.message_id
                            last_sent_text = part
                        await asyncio.sleep(TEXT_STREAM_DELAY)
                    full_response = chunks[-1]
        
        if buffer:
            full_response += buffer
            chunks = split_text_naturally(full_response)
            for i, part in enumerate(chunks):
                if i == 0 and part != last_sent_text:
                    await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=part)
                    last_sent_text = part
                elif i > 0:
                    message = await context.bot.send_message(chat_id=chat_id, text=part, reply_to_message_id=reply_to_message_id if ENABLE_MESSAGE_MENTION else None)
                    message_id = message.message_id
                    last_sent_text = part
                await asyncio.sleep(TEXT_STREAM_DELAY)
        
        user_history.append({"role": "user", "parts": current_parts})
        user_history.append({"role": "model", "parts": [full_response]})
        if len(user_history) > MAX_HISTORY:
            user_history = user_history[-MAX_HISTORY:]
        save_history(username, user_history)
        logger.info(f"Updated history for {username}")
        
    except Exception as e:
        logger.exception(f"Error in stream_text_response for chat_id {chat_id}: {str(e)}")
        if last_sent_text != TEXT_ERROR_MSG:
            await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=TEXT_ERROR_MSG)

async def stream_response(chat_id: int, content, username: str, context: ContextTypes.DEFAULT_TYPE, reply_to_message_id: int = None) -> None:
    """Stream media response chunk-by-chunk, optionally replying to the original message."""
    logger.info(f"Processing media request for chat_id {chat_id} from {username}")
    instruction = load_system_instruction(username)
    try:
        model_kwargs = {"system_instruction": instruction} if instruction else {}
        model = genai.GenerativeModel(MODEL_NAME, **model_kwargs)
    except Exception as e:
        logger.exception(f"Failed to initialize model for {username}: {str(e)}")
        await context.bot.send_message(chat_id=chat_id, text="I’m having trouble starting up. Please try again later!", reply_to_message_id=reply_to_message_id if ENABLE_MESSAGE_MENTION else None)
        return
    
    user_history = load_history(username)
    logger.info(f"Loaded history for {username}: {len(user_history)} entries")
    
    try:
        chat_session = model.start_chat(history=user_history)
    except Exception as e:
        logger.exception(f"Failed to start chat session for {username}: {str(e)}")
        await context.bot.send_message(chat_id=chat_id, text="I couldn’t start our chat. Please try again!", reply_to_message_id=reply_to_message_id if ENABLE_MESSAGE_MENTION else None)
        return
    
    parts = []
    for item in content:
        if isinstance(item, str):
            parts.append(item)
        elif isinstance(item, dict) and "mime_type" in item:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
            file_type = item["mime_type"].split("/")[0]
            file_ext = item["mime_type"].split("/")[1]
            file_name = f"{file_type}_{timestamp}.{file_ext}"
            file_path = os.path.join(get_user_folder(username), file_name)
            
            message = await context.bot.send_message(chat_id=chat_id, text=MEDIA_UPLOADING_MSG, reply_to_message_id=reply_to_message_id if ENABLE_MESSAGE_MENTION else None)
            message_id = message.message_id
            
            try:
                with open(file_path, 'wb') as f:
                    f.write(item["data"])
                logger.info(f"Saved {file_type} to {file_path}")
                uploaded_file = genai.upload_file(file_path, mime_type=item["mime_type"])
                parts.append(uploaded_file)
            except Exception as e:
                logger.error(f"Gemini upload failed for {file_type} at {file_path}: {str(e)}")
                await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=UPLOAD_ERROR_MSG)
                return
    
    current_parts = parts
    
    last_sent_text = MEDIA_UPLOADING_MSG
    try:
        if last_sent_text != MEDIA_PROCESSING_MSG:
            await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=MEDIA_PROCESSING_MSG)
            last_sent_text = MEDIA_PROCESSING_MSG
        full_response = ""
        buffer = ""
        
        response = chat_session.send_message(current_parts, stream=True)
        for chunk in response:
            chunk_text = chunk.text.strip()
            if chunk_text:
                buffer += chunk_text
                
                if len(buffer) >= 100 or buffer[-1] in " ।?!,;:\n":
                    if full_response and not full_response[-1].isspace() and not full_response[-1] in "।?!,;:\n":
                        full_response += " "
                    full_response += buffer
                    buffer = ""
                    
                    chunks = split_text_naturally(full_response)
                    for i, part in enumerate(chunks):
                        if i == 0 and part != last_sent_text:
                            await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=part)
                            last_sent_text = part
                        elif i > 0:
                            message = await context.bot.send_message(chat_id=chat_id, text=part, reply_to_message_id=reply_to_message_id if ENABLE_MESSAGE_MENTION else None)
                            message_id = message.message_id
                            last_sent_text = part
                        await asyncio.sleep(MEDIA_STREAM_DELAY)
                    full_response = chunks[-1]
        
        if buffer:
            if full_response and not full_response[-1].isspace() and not full_response[-1] in "।?!,;:\n":
                full_response += " "
            full_response += buffer
            chunks = split_text_naturally(full_response)
            for i, part in enumerate(chunks):
                if i == 0 and part != last_sent_text:
                    await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=part)
                    last_sent_text = part
                elif i > 0:
                    message = await context.bot.send_message(chat_id=chat_id, text=part, reply_to_message_id=reply_to_message_id if ENABLE_MESSAGE_MENTION else None)
                    message_id = message.message_id
                    last_sent_text = part
                await asyncio.sleep(MEDIA_STREAM_DELAY)
        
        if not full_response and last_sent_text != "I couldn’t generate a response for that.":
            await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="I couldn’t generate a response for that.")
        
        user_history.append({"role": "user", "parts": [part.uri if hasattr(part, 'uri') else part for part in current_parts]})
        user_history.append({"role": "model", "parts": [full_response]})
        if len(user_history) > MAX_HISTORY:
            user_history = user_history[-MAX_HISTORY:]
        save_history(username, user_history)
        logger.info(f"Updated history for {username}")
        
    except Exception as e:
        logger.exception(f"Error in stream_response for chat_id {chat_id}: {str(e)}")
        if last_sent_text != MEDIA_ERROR_MSG:
            await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=MEDIA_ERROR_MSG)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    username = user.username or str(user.id)
    chat_id = update.effective_chat.id
    text = update.message.text
    reply_to_message_id = update.message.message_id if ENABLE_MESSAGE_MENTION else None
    logger.info(f"Received text message from {username}: {text}")
    await stream_text_response(chat_id, text, username, context, reply_to_message_id)

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    username = user.username or str(user.id)
    chat_id = update.effective_chat.id
    file = update.message.photo[-1]
    caption = update.message.caption or "Explain this image"
    reply_to_message_id = update.message.message_id if ENABLE_MESSAGE_MENTION else None
    logger.info(f"Received image from {username} with caption: {caption}")
    
    try:
        file_obj = await file.get_file()
        file_url = file_obj.file_path
        folder_path = get_user_folder(username)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        save_path = os.path.join(folder_path, f"image_{timestamp}.jpg")
        
        response = requests.get(file_url, timeout=API_REQUEST_TIMEOUT)
        response.raise_for_status()
        with open(save_path, 'wb') as f:
            f.write(response.content)
        logger.info(f"Saved image to {save_path}")
        content = [caption, {"mime_type": "image/jpeg", "data": response.content}]
        await stream_response(chat_id, content, username, context, reply_to_message_id)
    
    except requests.RequestException as e:
        logger.error(f"Failed to download image for chat_id {chat_id}: {str(e)}")
        await context.bot.send_message(chat_id=chat_id, text=FETCH_ERROR_MSG.format(type="image"), reply_to_message_id=reply_to_message_id)
    except Exception as e:
        logger.exception(f"Error in handle_image for chat_id {chat_id}: {str(e)}")
        await context.bot.send_message(chat_id=chat_id, text="I had trouble with that image. Please try again!", reply_to_message_id=reply_to_message_id)

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    username = user.username or str(user.id)
    chat_id = update.effective_chat.id
    file = update.message.audio or update.message.voice
    caption = update.message.caption or "Take this as a normal message & answer if it seems something else than Transcribe and summarize this audio."
    reply_to_message_id = update.message.message_id if ENABLE_MESSAGE_MENTION else None
    logger.info(f"Received audio from {username} with caption: {caption}")
    
    try:
        file_obj = await file.get_file()
        file_url = file_obj.file_path
        folder_path = get_user_folder(username)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        save_path = os.path.join(folder_path, f"audio_{timestamp}.ogg")
        
        response = requests.get(file_url, timeout=API_REQUEST_TIMEOUT)
        response.raise_for_status()
        with open(save_path, 'wb') as f:
            f.write(response.content)
        logger.info(f"Saved audio to {save_path}")
        content = [caption, {"mime_type": "audio/ogg", "data": response.content}]
        await stream_response(chat_id, content, username, context, reply_to_message_id)
    
    except requests.RequestException as e:
        logger.error(f"Failed to download audio for chat_id {chat_id}: {str(e)}")
        await context.bot.send_message(chat_id=chat_id, text=FETCH_ERROR_MSG.format(type="audio"), reply_to_message_id=reply_to_message_id)
    except Exception as e:
        logger.exception(f"Error in handle_audio for chat_id {chat_id}: {str(e)}")
        await context.bot.send_message(chat_id=chat_id, text="I couldn’t process that audio. Please try again!", reply_to_message_id=reply_to_message_id)

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    username = user.username or str(user.id)
    chat_id = update.effective_chat.id
    file = update.message.video
    if not file:
        logger.warning(f"Expected video but got something else from {username}")
        return
    caption = update.message.caption or "What do you see in this video?"
    reply_to_message_id = update.message.message_id if ENABLE_MESSAGE_MENTION else None
    logger.info(f"Received video from {username} with caption: {caption}")
    
    try:
        file_obj = await file.get_file()
        file_url = file_obj.file_path
        folder_path = get_user_folder(username)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        save_path = os.path.join(folder_path, f"video_{timestamp}.mp4")
        
        response = requests.get(file_url, timeout=API_REQUEST_TIMEOUT)
        response.raise_for_status()
        with open(save_path, 'wb') as f:
            f.write(response.content)
        logger.info(f"Saved video to {save_path}")
        content = [caption, {"mime_type": "video/mp4", "data": response.content}]
        await stream_response(chat_id, content, username, context, reply_to_message_id)
    
    except requests.RequestException as e:
        logger.error(f"Failed to download video for chat_id {chat_id}: {str(e)}")
        await context.bot.send_message(chat_id=chat_id, text=FETCH_ERROR_MSG.format(type="video"), reply_to_message_id=reply_to_message_id)
    except Exception as e:
        logger.exception(f"Error in handle_video for chat_id {chat_id}: {str(e)}")
        await context.bot.send_message(chat_id=chat_id, text="I had an issue with that video. Please try again!", reply_to_message_id=reply_to_message_id)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    reply_to_message_id = update.message.message_id if ENABLE_MESSAGE_MENTION else None
    logger.info(f"Received /start command from chat_id {chat_id}")
    await context.bot.send_message(chat_id=chat_id, text=START_MSG, reply_to_message_id=reply_to_message_id)

async def set_instruction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    username = user.username or str(user.id)
    chat_id = update.effective_chat.id
    reply_to_message_id = update.message.message_id if ENABLE_MESSAGE_MENTION else None
    instruction = " ".join(context.args).strip()
    
    logger.info(f"Received /setinstruction from {username}")
    
    if not instruction:
        await context.bot.send_message(chat_id=chat_id, text="Please provide an instruction after the command! Usage: /setinstruction <your instruction>", reply_to_message_id=reply_to_message_id)
        return
    
    if save_system_instruction(username, instruction):
        await context.bot.send_message(chat_id=chat_id, text="Your custom instruction has been set successfully! It will take effect with your next message.", reply_to_message_id=reply_to_message_id)
    else:
        await context.bot.send_message(chat_id=chat_id, text="Sorry, I couldn’t save your instruction. Please try again!", reply_to_message_id=reply_to_message_id)

async def clean_instruction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    username = user.username or str(user.id)
    chat_id = update.effective_chat.id
    reply_to_message_id = update.message.message_id if ENABLE_MESSAGE_MENTION else None
    
    logger.info(f"Received /cleaninstruction from {username}")
    
    if delete_system_instruction(username):
        await context.bot.send_message(chat_id=chat_id, text="Your custom instruction has been removed! You’re now on the default instruction, effective with your next message.", reply_to_message_id=reply_to_message_id)
    else:
        await context.bot.send_message(chat_id=chat_id, text="No custom instruction found to remove, or there was an error.", reply_to_message_id=reply_to_message_id)

async def show_instruction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    username = user.username or str(user.id)
    chat_id = update.effective_chat.id
    reply_to_message_id = update.message.message_id if ENABLE_MESSAGE_MENTION else None
    
    logger.info(f"Received /showinstruction from {username}")
    
    instruction = load_user_instruction(username)
    if instruction:
        await context.bot.send_message(chat_id=chat_id, text=f"Your custom instruction is: \"{instruction}\"", reply_to_message_id=reply_to_message_id)
    else:
        await context.bot.send_message(chat_id=chat_id, text="You don’t have a custom instruction set. You’re on the default instruction.", reply_to_message_id=reply_to_message_id)

def main():
    try:
        application = Application.builder().token(TELEGRAM_TOKEN).build()
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("setinstruction", set_instruction))
        application.add_handler(CommandHandler("cleaninstruction", clean_instruction))
        application.add_handler(CommandHandler("showinstruction", show_instruction))
        application.add_handler(MessageHandler(filters.VIDEO & ~filters.PHOTO, handle_video))
        application.add_handler(MessageHandler(filters.PHOTO, handle_image))
        application.add_handler(MessageHandler(filters.AUDIO | filters.VOICE, handle_audio))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
        logger.info("Bot is starting...")
        application.run_polling()
    except Exception as e:
        logger.critical(f"Failed to start bot: {str(e)}")
        raise SystemExit("Bot failed to start. Check logs for details.")

if __name__ == "__main__":
    main()
