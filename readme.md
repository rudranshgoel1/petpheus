# 🐾 Petpheus

A Slack bot that turns profile pictures, images, and existing emojis into animated petpet GIFs and adds them as custom workspace emojis.

---

## what it does

- **pet a user** — mention someone and give a name, petpheus turns their pfp into a petpet emoji
- **pet an image** — upload any image with a name, petpheus turns it into a petpet emoji
- **pet an emoji** — use an existing workspace emoji and give it a new name, petpheus petpets it
- **home tab** — click petpheus in your sidebar to see and delete all the emojis you've made
- **thanks button** — click "thanks petpheus 🐾" after an emoji is made and petpheus will pet you back

---

## usage

### pet a user's pfp
```
@username emoji-name
```
example: `@stolen_username pet-rudransh`

### pet an uploaded image
upload an image and type the emoji name as the message caption.

### pet an existing emoji
```
:emoji-name: new-name
```
example: `:sob: pet-sob`

---

## setup

### prerequisites
- Python 3.8+
- A Slack app with the following scopes:
  - `chat:write`
  - `reactions:write`
  - `reactions:read`
  - `users:read`
  - `emoji:read`
  - `channels:history`
  - `app_mentions:read`
- A Neon (or any PostgreSQL) database
- The [patpatgifmaker](https://patpatgifmaker.vercel.app) API

### install dependencies
```bash
pip install slack-sdk slack-bolt flask slackeventsapi python-dotenv psycopg2-binary requests
```

### environment variables
create a `.env` file in the root of the project:

```env
SLACK_TOKEN=xoxb-...
USER_SLACK_TOKEN=xoxp-...
SLACK_SIGNING_SECRET=...
WORKSPACE_ID=your-workspace-name
DATABASE_URL=postgresql://...
VERSION=1.0.0

# user cookies for emoji.add (grab from browser devtools)
USER_COOKIE_B=...
USER_COOKIE_X=...
USER_COOKIE_D=...
URL_PARAMS=...
```

> **note:** `USER_SLACK_TOKEN` and the cookies are required because Slack's `emoji.add` API is not officially available to bots — petpheus uses a user token + browser cookies to upload emojis.

### slack app configuration

in your Slack app settings:

1. **Event Subscriptions** → set Request URL to `https://your-domain/slack/events`
   - subscribe to: `message.channels`, `app_home_opened`

2. **Interactivity & Shortcuts** → set Request URL to `https://your-domain/slack/interactions`

3. **App Home** → enable the Home Tab

### run locally
```bash
python bot.py
```

use [ngrok](https://ngrok.com) to expose your local server to Slack during development:
```bash
ngrok http 5000
```

---

## database

petpheus uses PostgreSQL to track which user created each emoji. the table is created automatically on startup:

```sql
CREATE TABLE IF NOT EXISTS emojis (
    name TEXT PRIMARY KEY,
    created_by TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## deployment

petpheus is deployed on **Vercel** as a Python Flask app. since Vercel has no persistent filesystem, all state is stored in Neon PostgreSQL.

make sure all environment variables are set in your Vercel project settings.

---

## project structure

```
petpheus/
├── bot.py          # main bot logic
├── .env            # environment variables (not committed)
└── requirements.txt
```