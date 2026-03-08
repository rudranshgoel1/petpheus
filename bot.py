import slack
import os
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from slackeventsapi import SlackEventAdapter
import hashlib
import hmac
import time
import requests

env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

app = Flask(__name__)
slack_event_adapter = SlackEventAdapter(os.environ['SLACK_SIGNING_SECRET'],'/slack/events',app)

client = slack.WebClient(token=os.environ["SLACK_TOKEN"])

BOT_ID = client.api_call("auth.test")['user_id']

def verify_slack_signature(req):
    slack_signing_secret = os.environ['SLACK_SIGNING_SECRET'].encode()
    timestamp = req.headers.get('X-Slack-Request-Timestamp')

    if abs(time.time() - int(timestamp)) > 60 * 5:
        return False
    
    sig_basestring = f"v0:{timestamp}:{req.get_data(as_text=True)}"
    my_signature = 'v0=' + hmac.new(slack_signing_secret, sig_basestring.encode(), hashlib.sha256).hexdigest()
    slack_signature = req.headers.get('X-Slack-Signature', '')

    return hmac.compare_digest(my_signature, slack_signature)

@app.route('/slack/events', methods=['POST'])
def slack_events():
    if not verify_slack_signature(request):
        return "invalid signature", 403

    data = request.json

    if data.get('type') == 'url_verification':
        return jsonify({'challenge': data['challenge']})
    
    if data.get('type') == 'event_callback':
        event = data.get('event', {})
        print(f"Event received: {event}")

    return jsonify({'status': 'ok'})

@slack_event_adapter.on('message')
def message(payload):
    print(payload)
    event = payload.get('event', {})
    channel_id = event.get('channel')
    user_id = event.get('user')
    text = event.get('text', '')
    files = event.get('files', [])

    if BOT_ID != user_id:
        if '##' in text:
            return
        elif files: 
            file = files[0]

            if file['mimetype'].startswith('image'):
                image_url = file['url_private']

                ts = event.get('ts')
                client.reactions_add(channel=channel_id, name='loading', timestamp=ts)
                client.chat_postMessage(channel=channel_id, thread_ts=ts, text="making emoji... (not rn it is still in development)")


                r = requests.get("https://patpatgifmaker.vercel.app/api/petpet", params={
                    "image_url": image_url,
                    "slack_token": os.environ["SLACK_TOKEN"],
                })
                gif_url = r.json()["gif_url"]

        else:
            return

if __name__ == "__main__":
    app.run(debug=True)