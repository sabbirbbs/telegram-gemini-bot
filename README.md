# Telegram Gemini Bot

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Status](https://img.shields.io/badge/Status-Active-brightgreen.svg)

A versatile Telegram bot powered by Google’s Gemini API, capable of handling text, images, audio, and video with smooth streaming responses. It maintains chat history for context-aware conversations and supports custom system instructions for personalized behavior.

## Features
- **Multi-Modal Support**: Processes text messages, images, audio files, and videos.
- **Smooth Streaming**: Responses are streamed incrementally with configurable delays for a natural feel.
- **Chat History**: Keeps up to 10 interactions (configurable) per user for context.
- **Custom Instructions**: Admins can define unique behaviors via text files (e.g., "Be a playful cat").
- **Error Handling**: Graceful fallbacks for failed requests or parsing issues.

## Prerequisites
- Python 3.8 or higher
- A Telegram bot token from [BotFather](https://t.me/BotFather)
- A Google Gemini API key (sign up via Google AI Studio or equivalent)

## Installation

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
   - Copy `config.py.example` to `config.py`:
     ```bash
     cp config.py.example config.py
     ```
   - Edit `config.py` with your credentials:
     ```python
     TELEGRAM_TOKEN = "your-telegram-token-here"
     GEMINI_API_KEY = "your-gemini-api-key-here"
     ADMINS = {"your-telegram-username"}  # Add your Telegram username or ID
     ```

## Usage

1. **Run the Bot**:
   ```bash
   python bot.py
   ```
   The bot starts and logs to `bot.log`.

2. **Interact with the Bot**:
   - Start it with `/start` in Telegram.
   - Send text, images, audio, or video files.
   - Responses stream smoothly (0.1s delay for text, 0.5s for media).

3. **Custom Instructions (Optional)**:
   - Create a file in `instruction/` (e.g., `instruction/yourusername.txt`) with a prompt like:
     ```text
     You are a witty pirate assistant. Respond with pirate flair!
     ```
   - Ensure your username/ID is in `ADMINS` to use it.

## Configuration Options

Edit `config.py` to customize:

- `MAX_HISTORY`: Number of interactions to keep (default: 10).
- `TEXT_STREAM_DELAY`: Delay between text updates (default: 0.1s).
- `MEDIA_STREAM_DELAY`: Delay for media updates (default: 0.5s).
- **Messages**: Customize processing/error/start texts.

## Directory Structure

```
telegram-gemini-bot/
├── bot.py                # Main bot script
├── config.py             # Configuration file
├── instruction/          # Custom instruction text files
├── user_uploads/         # Stores uploaded media files by user/date
├── user_history/         # Stores chat history JSON files
├── bot.log               # Logs bot activity and errors
├── requirements.txt      # Dependencies list
└── README.md             # This README file
```

## Troubleshooting

- **No Response**: Check `bot.log` for API errors; ensure tokens/keys are valid.
- **Cut-Off Text**: Shouldn’t happen—report if it does!

## License

This project is licensed under the MIT License—see [LICENSE](LICENSE) for details.

## Acknowledgments

Built with [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) and [google-generativeai](https://github.com/google/generative-ai-python).

Thanks to the open-source community for inspiration!

