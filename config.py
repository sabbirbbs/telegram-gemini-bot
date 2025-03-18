# config.py - Configuration settings for the Telegram bot

TELEGRAM_TOKEN = "637724577785:AAGVi56ygefsfes849xgfrrN11Z10Ufse4"
GEMINI_API_KEY = "AIdsadeYwewTLwewmNNqwewNtN8A"
BASE_DIR = "user_uploads"
HISTORY_DIR = "user_history"
INSTRUCTION_DIR = "instruction"
MODEL_NAME = "gemini-2.0-flash"
MAX_HISTORY = 10
TEXT_STREAM_DELAY = 0.1
MEDIA_STREAM_DELAY = 0.5
API_REQUEST_TIMEOUT = 10
ENABLE_MESSAGE_MENTION = True
TEXT_PROCESSING_MSG = "Thinking..."
MEDIA_UPLOADING_MSG = "Uploading your file..."
MEDIA_PROCESSING_MSG = "Processing your request..."
TEXT_ERROR_MSG = "I got stuck thinking about that. Could you ask again?"
MEDIA_ERROR_MSG = "Something went off track. Could you try again?"
UPLOAD_ERROR_MSG = "I couldn’t upload your file. Please try again!"
FETCH_ERROR_MSG = "I couldn’t fetch that {type}. Could you send it again?"
START_MSG = "Hi there! I’m your friendly bot, ready to chat about text, images, audio, and video. How can I assist you today?"
