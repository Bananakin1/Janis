# Setup Instructions

## Prerequisites

- Python 3.11+
- Obsidian desktop app installed
- Discord account
- Azure OpenAI resource with deployed model

---

## 1. Discord Bot Setup

### Create Application

1. Go to https://discord.com/developers/applications
2. Click **New Application**
3. Name it (e.g., "Obsidian Notes Bot")
4. Click **Create**

### Configure Bot

1. Navigate to **Bot** in left sidebar
2. Click **Reset Token** and copy the token (save it for `.env`)
3. Enable these **Privileged Gateway Intents**:
   - MESSAGE CONTENT INTENT (required)
4. Click **Save Changes**

### Generate Invite URL

1. Navigate to **OAuth2 > URL Generator**
2. Select scopes: `bot`
3. Select permissions:
   - Read Messages/View Channels
   - Send Messages
   - Add Reactions
4. Copy the generated URL
5. Open URL in browser, select your server, authorize

### Get Channel ID

1. In Discord, go to **User Settings > Advanced**
2. Enable **Developer Mode**
3. Right-click the channel you want to monitor
4. Click **Copy Channel ID** (save for `.env`)

---

## 2. Obsidian Local REST API Setup

### Install Plugin

1. Open Obsidian
2. Go to **Settings > Community plugins**
3. Disable **Restricted mode** if prompted
4. Click **Browse** and search for "Local REST API"
5. Install and enable the plugin

### Configure Plugin

1. Go to **Settings > Local REST API**
2. Note the **Port** (default: 27124)
3. Click **Copy API Key** (save for `.env`)
4. Ensure **Enable HTTPS** is checked

### Verify Connection

Open browser and navigate to:
```
https://127.0.0.1:27124
```
Accept the self-signed certificate warning. You should see the API documentation.

---

## 3. Azure OpenAI Setup

### Get Credentials

From your Azure OpenAI resource:

1. Go to **Keys and Endpoint** in Azure Portal
2. Copy **Endpoint** (e.g., `https://your-resource.openai.azure.com/`)
3. Copy **Key 1** or **Key 2**
4. Note your **Deployment name** (e.g., `gpt-4o`)

---

## 4. Python Environment Setup

### Clone and Install

```bash
cd /mnt/c/dev/discord-obsidian-agent
python -m venv .venv
source .venv/bin/activate  # On Windows WSL
pip install -e .
```

### Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your values:

```bash
# Discord
DISCORD_TOKEN=your_bot_token_here
DISCORD_CHANNEL_ID=123456789012345678

# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your_api_key_here
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_API_VERSION=2024-08-01-preview

# Obsidian
OBSIDIAN_VAULT_PATH=/mnt/c/Users/YourName/Documents/ObsidianVault
OBSIDIAN_API_HOST=127.0.0.1
OBSIDIAN_API_PORT=27124
OBSIDIAN_API_KEY=your_obsidian_api_key_here

# Optional
DEFAULT_NOTE_FOLDER=Inbox
```

---

## 5. Run the Agent

### Start Obsidian

Ensure Obsidian is running with your vault open (Local REST API requires Obsidian to be running).

### Start the Bot

```bash
cd /mnt/c/dev/discord-obsidian-agent
source .venv/bin/activate
python -m src.main
```

Expected output:
```
2026-01-20 ... | INFO | Starting Discord-Obsidian Agent...
2026-01-20 ... | INFO | Refreshing vault index from /path/to/vault
2026-01-20 ... | INFO | Indexed 150 notes
2026-01-20 ... | INFO | Bot logged in as Obsidian Notes Bot#1234
```

### Test

In your Discord channel, send a message:
```
Create a note about my meeting with Sarah Chen today.
We discussed the Q2 budget and project timeline.
```

The bot should respond confirming the note was created.

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Bot doesn't respond | Check DISCORD_CHANNEL_ID matches the channel |
| "Message content intent" error | Enable MESSAGE CONTENT INTENT in Discord Developer Portal |
| Connection refused to Obsidian | Ensure Obsidian is running with vault open |
| SSL certificate error | Expected - REST API uses self-signed cert, httpx verify=False handles this |
| "Note not found" | Check OBSIDIAN_VAULT_PATH is correct absolute path |

---

## File Locations Summary

| Item | Location |
|------|----------|
| Discord Bot Token | Discord Developer Portal > Bot > Token |
| Discord Channel ID | Right-click channel > Copy Channel ID |
| Azure OpenAI Endpoint | Azure Portal > OpenAI Resource > Keys and Endpoint |
| Azure OpenAI Key | Azure Portal > OpenAI Resource > Keys and Endpoint |
| Obsidian API Key | Obsidian > Settings > Local REST API > Copy API Key |
| Vault Path | Your local Obsidian vault folder (absolute path) |
