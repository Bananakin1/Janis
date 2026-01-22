# Janis - Discord-Obsidian Agent

A Discord bot that manages your Obsidian vault through natural language. Send messages to Discord, and Janis will create, update, and search notes in your vault using Azure OpenAI.

## What It Does

- **Create notes** - "Create a meeting note for today's call with Jacob Lee about Remy's pooping schedule"
- **Update notes** - "Add action items to the Jacob Lee note: poop consistency, medicines, 'is he still eating Nala's food?'"
- **Search & read** - "How liquid was Remy's poop last week?"
- **Smart linking** - Automatically creates wikilinks to related notes and hub pages

Janis uses a tool-calling loop to intelligently decide when to search, read, or write notes based on your request.

## Requirements

- Python 3.11+
- [Obsidian](https://obsidian.md) with Local REST API plugin
- Discord account with a bot
- Azure OpenAI credentials (contact Victor for access)

## Installation

### 1. Install Obsidian

Download and install Obsidian from [obsidian.md/download](https://obsidian.md/download).

### 2. Set Up Obsidian Local REST API Plugin

1. Open Obsidian and go to **Settings** (gear icon)
2. Navigate to **Community plugins**
3. Click **Turn on community plugins** if prompted
4. Click **Browse** and search for "Local REST API"
5. Click **Install**, then **Enable**
6. Go to **Settings > Community plugins > Local REST API** to configure:
   - Copy the **API Key** (auto-generated)
   - Note the **Port** (default: `27124`)
   - Note the **Host** (default: `127.0.0.1`)

Your vault path is the folder where your `.obsidian` directory lives (e.g., `C:\Users\You\Documents\MyVault`).

### 3. Create a Discord Bot

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Click **New Application** and give it a name
3. Navigate to the **Bot** tab and click **Add Bot**
4. Under **Privileged Gateway Intents**, enable **Message Content Intent**
5. Click **Reset Token** and copy the bot token (save it securely - you can only view it once)
6. Go to **OAuth2 > URL Generator**:
   - Select scopes: `bot`
   - Select permissions: `Send Messages`, `Read Message History`
7. Copy the generated URL and open it to invite the bot to your server

### 4. Get Your Discord Channel ID

1. In Discord, go to **User Settings > Advanced** and enable **Developer Mode**
2. Right-click the channel where you want the bot to listen
3. Click **Copy Channel ID**

### 5. Configure Environment

Clone the repository and create a `.env` file:

```bash
git clone https://github.com/your-repo/janis.git
cd janis
cp .env.example .env  # or create .env manually
```

Fill in your `.env` taking as reference the .env.example file:

```env
# Discord
DISCORD_TOKEN=your_bot_token_here
DISCORD_CHANNEL_ID=your_channel_id_here

# Azure OpenAI (ask Victor for credentials)
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_API_KEY=your_api_key_here
AZURE_OPENAI_DEPLOYMENT=gpt-4o

# Obsidian
OBSIDIAN_VAULT_PATH=C:\Users\You\Documents\MyVault
OBSIDIAN_API_KEY=your_obsidian_api_key_here
OBSIDIAN_API_HOST=127.0.0.1
OBSIDIAN_API_PORT=27124

# Optional
DEFAULT_NOTE_FOLDER=Inbox
REASONING_EFFORT=medium
```

> **Azure AI Credentials**: Contact Victor privately to obtain the Azure OpenAI endpoint and API key.

### 6. Install Dependencies

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

pip install -e ".[dev]"
```

### 7. Run the Bot

```bash
python -m src.main
```

## Running on Startup

### Windows (Task Scheduler + Batch File)

1. Create `start_janis.bat` in your project folder:

```batch
@echo off
cd /d C:\path\to\janis
call venv\Scripts\activate
python -m src.main
```

2. Open **Task Scheduler** (`Win+R`, type `taskschd.msc`)
3. Click **Create Task** (not "Create Basic Task")
4. **General tab**: Name it "Janis Bot", check "Run only when user is logged on"
5. **Triggers tab**: Click New, select "At log on"
6. **Actions tab**: Click New, select "Start a program"
   - Program: `C:\path\to\janis\start_janis.bat`
   - Start in: `C:\path\to\janis`
7. Click OK

### macOS/Linux (launchd / systemd)

**macOS (launchd):**

1. Create `start_janis.sh`:

```bash
#!/bin/bash
cd /path/to/janis
source venv/bin/activate
python -m src.main
```

2. Make it executable: `chmod +x start_janis.sh`

3. Create `~/Library/LaunchAgents/com.janis.bot.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.janis.bot</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/janis/start_janis.sh</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/janis.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/janis.err</string>
</dict>
</plist>
```

4. Load the agent:

```bash
launchctl load ~/Library/LaunchAgents/com.janis.bot.plist
```

**Linux (systemd user service):**

1. Create `~/.config/systemd/user/janis.service`:

```ini
[Unit]
Description=Janis Discord-Obsidian Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=/path/to/janis
ExecStart=/path/to/janis/venv/bin/python -m src.main
Restart=on-failure

[Install]
WantedBy=default.target
```

2. Enable and start:

```bash
systemctl --user enable janis
systemctl --user start janis
```

## Runtime Requirements

For Janis to work, you must have:

1. **Obsidian running** with the vault open (the REST API plugin only works when Obsidian is open)
2. **Internet connection** for Discord and Azure OpenAI
3. **The bot script running** (via `python -m src.main` or startup automation)

## Testing

Run the smoke test to verify everything is configured:

```bash
python scripts/smoke_test.py
```

Run unit tests:

```bash
python -m pytest tests/unit/ -v
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Obsidian is not running" | Open Obsidian with your vault |
| Bot not responding | Check `DISCORD_CHANNEL_ID` matches the channel you're messaging |
| API errors | Verify your Azure credentials with Victor |
| SSL certificate errors | Expected for local Obsidian REST API (uses self-signed cert) |

## License

MIT
