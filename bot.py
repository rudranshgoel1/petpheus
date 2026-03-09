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
userclient = slack.WebClient(token=os.environ["USER_SLACK_TOKEN"])
usercookie = os.environ["USER_COOKIE"]
workspaceid = os.environ["WORKSPACE_ID"]

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
        elif files and text: 
            file = files[0]

            if file['mimetype'].startswith('image'):
                image_url = file['url_private']

                ts = event.get('ts')
                client.reactions_add(channel=channel_id, name='loading', timestamp=ts)
                client.chat_postMessage(channel=channel_id, thread_ts=ts, text="making emoji...")

                r = requests.get("https://patpatgifmaker.vercel.app/api/petpet", params={
                    "image_url": image_url,
                    "slack_token": os.environ["SLACK_TOKEN"],
                })
                gif_url = r.json()["gif_url"]

                gif = requests.get(gif_url)

                files = {
                    "image": ("emoji.gif", gif.content, "image/gif")
                }
                
                data = {
                    "token": os.environ["USER_SLACK_TOKEN"],
                    "name": text,
                    "mode": "url",
                    "url": gif_url,
                    "search_args": "{}",
                    "_x_reason": "add-custom-emoji-dialog-content",
                    "_x_mode": "online",
                    "_x_sonic": "true",
                    "_x_app_name": "client",
                }

                headers = {
                    "accept": "*/*",
                    "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
                    "priority": "u=1, i",
                    "sec-ch-ua": '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
                    "sec-ch-ua-mobile": "?0",
                    "sec-ch-ua-platform": '"macOS"',
                    "sec-fetch-dest": "empty",
                    "sec-fetch-mode": "cors",
                    "sec-fetch-site": "same-site",
                }
                
                cookies = {
                    "utm": "{}",
                    "b": os.environ["USER_COOKIE_B"],
                    "tz": "330",
                    "c": '{"banner_homepage_slackbot":1}',
                    "d-s": "1773046862",
                    "x": os.environ["USER_COOKIE_X"],
                    "d": os.environ["USER_COOKIE_D"],
                }

                emojir = requests.post(f"https://{workspaceid}.slack.com/api/emoji.add" + os.environ["URL_PARAMS"], headers=headers, cookies=cookies, data=data)
                
                emojir_json = emojir.json()
                print(emojir_json)
                
                # userclient.admin_emoji_add(name=text, url=gif_url)
                client.chat_postMessage(channel=channel_id, thread_ts=ts, text=f"emoji added :{text}:")
                client.reactions_remove(channel=channel_id, name='loading', timestamp=ts)
                client.reactions_add(channel=channel_id, name=text, timestamp=ts)

        elif files and not text:
            ts = event.get('ts')

            client.reactions_add(channel=channel_id, name='wrong', timestamp=ts)
            client.chat_postMessage(channel=channel_id, thread_ts=ts, text="bro send the emoji name atleast :skulk:")

        else:
            return

if __name__ == "__main__":
    app.run(debug=True)