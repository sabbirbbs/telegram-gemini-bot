# Telegram Gemini Bot

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg) ![License](https://img.shields.io/badge/License-MIT-green.svg) ![Status](https://img.shields.io/badge/Status-Active-brightgreen.svg)

A powerful and adaptable Telegram bot leveraging Google’s Gemini API, capable of processing text, images, audio, and video while delivering smooth streaming responses. It maintains chat history for contextual conversations and allows users to define personalized instructions.

## Key Features
- **Multi-Modal Support**: Handles text, images, audio files, and video content.
- **Streaming Responses**: Outputs text and media incrementally for a natural conversation flow.
- **Chat Memory**: Retains up to 10 interactions per user (adjustable).
- **Custom Instructions**: Users can personalize responses with `/setinstruction`, remove them with `/cleaninstruction`, and view them with `/showinstruction`.
- **Message Mention Control**: Toggle replies to user messages via `config.py`.
- **Robust Error Handling**: Ensures smooth operation and error resilience.
- **Partially Used in Another Bot**: Some of its functionality is integrated into [@sbmcenglishbot](https://t.me/sbmcenglishbot), showcasing its capabilities.

## Requirements
- Python 3.8+
- Telegram bot token from [BotFather](https://t.me/BotFather)
- Google Gemini API key (available via Google AI Studio or similar services)

## Installation & Setup

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/sabbirbbs/telegram-gemini-bot.git
   cd telegram-gemini-bot
   ```
2. **Install Dependencies**:
   ```bash
   pip install python-telegram-bot==21.10 google-generativeai requests
   ```
3. **Configure the Bot**:
   Edit `config.py` with your credentials:
   ```python
   TELEGRAM_TOKEN = "your-telegram-token-here"
   GEMINI_API_KEY = "your-gemini-api-key-here"
   ENABLE_MESSAGE_MENTION = True  # Set to False to disable message replies
   ```

## Running the Bot
```bash
python bot.py
```
Once started, logs will be recorded in `bot.log`.

## Usage
- Start by sending `/start` on Telegram.
- Send text, images, audio, or videos, and receive streamed responses.
- Customize behavior with:
  - `/setinstruction` to define a custom behavior.
  - `/showinstruction` to view the current instruction.
  - `/cleaninstruction` to reset instructions.

## Configuration Options (`config.py`)
- `MAX_HISTORY`: Number of past messages stored (default: 10).
- `TEXT_STREAM_DELAY`: Time interval for streaming text responses (default: 0.1s).
- `MEDIA_STREAM_DELAY`: Delay for media responses (default: 0.5s).
- `ENABLE_MESSAGE_MENTION`: Toggle direct replies to messages (default: True).

## Project Structure
```
telegram-gemini-bot/
├── bot.py                # Core bot script
├── config.py             # Configuration settings
├── instruction/          # User-defined instructions storage
├── user_uploads/         # Uploaded media files
├── user_history/         # Chat history storage
├── bot.log               # Log file
├── requirements.txt      # Dependencies list
└── README.md             # Documentation
```

## Troubleshooting
- **No Response**: Check `bot.log` for errors and verify API keys.
- **Custom Instructions Not Working**: Ensure the instruction file is correctly saved and send a new message after setting it.
- **Message Reply Issues**: Confirm `ENABLE_MESSAGE_MENTION` is properly set and restart the bot.

## License
This project is licensed under the MIT License—see `LICENSE` for details.

## Acknowledgments
Built with `python-telegram-bot` and `google-generativeai`, with inspiration from the open-source community.

