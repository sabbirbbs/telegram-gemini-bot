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
        logger.info(f"Checking instruction for username: {username}")
        logger.info(f"Admins configured: {ADMINS}")
        if username in ADMINS:
            admin_file = os.path.join(INSTRUCTION_DIR, f"{username}.txt")
            logger.info(f"Looking for admin file: {admin_file}")
            if os.path.exists(admin_file):
                with open(admin_file, 'r', encoding='utf-8') as f:
                    instruction = f.read().strip()
                    logger.info(f"Admin instruction found for {username}: {instruction}")
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

async def stream_text_response(chat_id: int, content, username: str, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Stream response chunks for text messages smoothly with configurable delay."""
    logger.info(f"Processing text request for chat_id {chat_id} from {username}")
    instruction = load_system_instruction(username)
    try:
        model_kwargs = {"system_instruction": instruction} if instruction else {}
        model = genai.GenerativeModel(MODEL_NAME, **model_kwargs)
    except Exception as e:
        logger.exception(f"Failed to initialize model for {username}: {str(e)}")
        await context.bot.send_message(chat_id=chat_id, text="I’m having trouble starting up. Please try again later!")
        return
    
    user_history = load_history(username)
    logger.info(f"Loaded history for {username}: {len(user_history)} entries")
    
    try:
        chat_session = model.start_chat(history=user_history)
    except Exception as e:
        logger.exception(f"Failed to start chat session for {username}: {str(e)}")
        await context.bot.send_message(chat_id=chat_id, text="I couldn’t start our chat. Please try again!")
        return
    
    current_parts = [content]
    
    message = await context.bot.send_message(chat_id=chat_id, text=TEXT_PROCESSING_MSG)
    message_id = message.message_id
    
    try:
        full_response = ""
        last_sent_response = TEXT_PROCESSING_MSG
        response = chat_session.send_message(current_parts, stream=True)
        
        for chunk in response:
            chunk_text = chunk.text.strip()
            if chunk_text:
                if full_response and not full_response[-1].isspace() and not full_response[-1] in ".!?,;:":
                    full_response += " "
                full_response += chunk_text
                if full_response != last_sent_response:
                    await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=full_response)
                    last_sent_response = full_response
                    logger.info(f"Updated text message for {username} with chunk: {chunk_text}")
                await asyncio.sleep(TEXT_STREAM_DELAY)
        
        if full_response != last_sent_response:
            if len(full_response) > 4096:
                parts = [full_response[i:i+4096] for i in range(0, len(full_response), 4096)]
                for i, part in enumerate(parts):
                    if i == 0:
                        await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=part)
                    else:
                        await context.bot.send_message(chat_id=chat_id, text=part)
                    await asyncio.sleep(TEXT_STREAM_DELAY)
            else:
                await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=full_response)
        
        user_history.append({"role": "user", "parts": current_parts})
        user_history.append({"role": "model", "parts": [full_response]})
        if len(user_history) > MAX_HISTORY:
            user_history = user_history[-MAX_HISTORY:]
        save_history(username, user_history)
        logger.info(f"Updated history for {username}")
        
    except Exception as e:
        logger.exception(f"Error in stream_text_response for chat_id {chat_id}: {str(e)}")
        await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=TEXT_ERROR_MSG)

async def stream_response(chat_id: int, content, username: str, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle response streaming for media with configurable delay."""
    logger.info(f"Processing media request for chat_id {chat_id} from {username}")
    instruction = load_system_instruction(username)
    try:
        model_kwargs = {"system_instruction": instruction} if instruction else {}
        model = genai.GenerativeModel(MODEL_NAME, **model_kwargs)
    except Exception as e:
        logger.exception(f"Failed to initialize model for {username}: {str(e)}")
        await context.bot.send_message(chat_id=chat_id, text="I’m having trouble starting up. Please try again later!")
        return
    
    user_history = load_history(username)
    logger.info(f"Loaded history for {username}: {len(user_history)} entries")
    
    try:
        chat_session = model.start_chat(history=user_history)
    except Exception as e:
        logger.exception(f"Failed to start chat session for {username}: {str(e)}")
        await context.bot.send_message(chat_id=chat_id, text="I couldn’t start our chat. Please try again!")
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
            
            message = await context.bot.send_message(chat_id=chat_id, text=MEDIA_UPLOADING_MSG)
            message_id = message.message_id
            
            try:
                with open(file_path, 'wb') as f:
                    f.write(item["data"])
                logger.info(f"Saved {file_type} to {file_path}")
                try:
                    uploaded_file = genai.upload_file(file_path, mime_type=item["mime_type"])
                    parts.append(uploaded_file)
                except Exception as e:
                    logger.error(f"Gemini upload failed for {file_type} at {file_path}: {str(e)}")
                    await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=UPLOAD_ERROR_MSG)
                    return
                # os.remove(file_path)  # Commented out to keep files for debugging
            except Exception as e:
                logger.exception(f"Error saving or uploading {file_type} for chat_id {chat_id}: {str(e)}")
                await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=UPLOAD_ERROR_MSG)
                return
    current_parts = parts
    
    try:
        await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=MEDIA_PROCESSING_MSG)
        full_response = ""
        last_update_time = 0
        
        response = chat_session.send_message(current_parts, stream=True)
        for chunk in response:
            chunk_text = chunk.text.strip()
            if chunk_text:
                if full_response and not full_response[-1].isspace() and not full_response[-1] in ".!?,;:":
                    full_response += " "
                full_response += chunk_text
                current_time = datetime.datetime.now().timestamp()
                if current_time - last_update_time >= MEDIA_STREAM_DELAY:
                    await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=full_response)
                    last_update_time = current_time
                    logger.info(f"Updated message for {username} with chunk: {chunk_text}")
        
        if not full_response:
            await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="I couldn’t generate a response for that.")
        else:
            if len(full_response) > 4096:
                parts = [full_response[i:i+4096] for i in range(0, len(full_response), 4096)]
                for i, part in enumerate(parts):
                    if i == 0:
                        await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=part)
                    else:
                        await context.bot.send_message(chat_id=chat_id, text=part)
                    await asyncio.sleep(MEDIA_STREAM_DELAY)
            else:
                await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=full_response)
        
        user_history.append({"role": "user", "parts": [part.uri if hasattr(part, 'uri') else part for part in current_parts]})
        user_history.append({"role": "model", "parts": [full_response]})
        if len(user_history) > MAX_HISTORY:
            user_history = user_history[-MAX_HISTORY:]
        save_history(username, user_history)
        logger.info(f"Updated history for {username}")
        
    except Exception as e:
        logger.exception(f"Error in stream_response for chat_id {chat_id}: {str(e)}")
        await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=MEDIA_ERROR_MSG)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    username = user.username or str(user.id)
    chat_id = update.effective_chat.id
    text = update.message.text
    logger.info(f"Received text message from {username}: {text}")
    await stream_text_response(chat_id, text, username, context)

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    username = user.username or str(user.id)
    chat_id = update.effective_chat.id
    file = update.message.photo[-1]
    caption = update.message.caption or "Explain this image"
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
        await stream_response(chat_id, content, username, context)
    
    except requests.RequestException as e:
        logger.error(f"Failed to download image for chat_id {chat_id}: {str(e)}")
        await context.bot.send_message(chat_id=chat_id, text=FETCH_ERROR_MSG.format(type="image"))
    except Exception as e:
        logger.exception(f"Error in handle_image for chat_id {chat_id}: {str(e)}")
        await context.bot.send_message(chat_id=chat_id, text="I had trouble with that image. Please try again!")

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    username = user.username or str(user.id)
    chat_id = update.effective_chat.id
    file = update.message.audio or update.message.voice
    caption = update.message.caption or "Take this as a normal message & answer if it seems something else than Transcribe and summarize this audio."
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
        await stream_response(chat_id, content, username, context)
    
    except requests.RequestException as e:
        logger.error(f"Failed to download audio for chat_id {chat_id}: {str(e)}")
        await context.bot.send_message(chat_id=chat_id, text=FETCH_ERROR_MSG.format(type="audio"))
    except Exception as e:
        logger.exception(f"Error in handle_audio for chat_id {chat_id}: {str(e)}")
        await context.bot.send_message(chat_id=chat_id, text="I couldn’t process that audio. Please try again!")

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    username = user.username or str(user.id)
    chat_id = update.effective_chat.id
    file = update.message.video
    if not file:
        logger.warning(f"Expected video but got something else from {username}")
        return
    caption = update.message.caption or "What do you see in this video?"
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
        await stream_response(chat_id, content, username, context)
    
    except requests.RequestException as e:
        logger.error(f"Failed to download video for chat_id {chat_id}: {str(e)}")
        await context.bot.send_message(chat_id=chat_id, text=FETCH_ERROR_MSG.format(type="video"))
    except Exception as e:
        logger.exception(f"Error in handle_video for chat_id {chat_id}: {str(e)}")
        await context.bot.send_message(chat_id=chat_id, text="I had an issue with that video. Please try again!")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    logger.info(f"Received /start command from chat_id {chat_id}")
    await context.bot.send_message(chat_id=chat_id, text=START_MSG)

def main():
    try:
        application = Application.builder().token(TELEGRAM_TOKEN).build()
        application.add_handler(CommandHandler("start", start))
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
