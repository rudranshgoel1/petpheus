import slack
import os
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from slackeventsapi import SlackEventAdapter
import hashlib
import hmac
import time
import re
import requests

env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

app = Flask(__name__)
slack_event_adapter = SlackEventAdapter(os.environ['SLACK_SIGNING_SECRET'],'/slack/events',app)

client = slack.WebClient(token=os.environ["SLACK_TOKEN"])
userclient = slack.WebClient(token=os.environ["USER_SLACK_TOKEN"])
workspaceid = os.environ["WORKSPACE_ID"]
version = os.environ["VERSION"]

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

def fix_emoji_name(name):
    name = name.lower()
    name = name.replace(' ', '-')
    name = re.sub(r'[^a-z0-9_-]', '', name)
    return name

def get_user_pfp(user_id):
    response = client.users_info(user=user_id)
    profile = response['user']['profile']
    
    for size in ['image_512', 'image_192', 'image_72', 'image_48', 'image_32']:
        if profile.get(size):
            return profile[size]
    return None        

@slack_event_adapter.on('message')
def message(payload):
    print(payload)
    event = payload.get('event', {})
    channel_id = event.get('channel')
    user_id = event.get('user')
    text = event.get('text', '')
    files = event.get('files', [])

    if BOT_ID != user_id:
        ping_match = re.match(r'<@([A-Z0-9]+)>\s+(\S+)$', text.strip())
        emoji_pet_match = re.match(r':([a-zA-Z0-9_-]+):\s+(\S+)$', text.strip())
        
        if event.get('bot_id') or event.get('subtype') == 'bot_message':
            return
        
        elif event.get('thread_ts') and event.get('thread_ts') != event.get('ts'):
            return
        
        elif emoji_pet_match and not files and not ping_match:
            source = emoji_pet_match.group(1)
            new_name = fix_emoji_name(emoji_pet_match.group(2))
            ts = event.get('ts')
            
            existing = client.api_call("emoji.list")
            all_emoji = existing.get('emoji', {})
            
            if new_name in all_emoji:
                client.chat_postMessage(channel=channel_id, thread_ts=ts, text="emoji with that name already exists :thinkies:")
                client.chat_postMessage(channel=channel_id, thread_ts=ts, text="uhh send this again with another name")
                return
            
            emoji_url = all_emoji.get(source)
            
            if not emoji_url:
                client.chat_postMessage(channel=channel_id, thread_ts=ts, text=f"couldn't find :{source}: emoji in the workspace brotato chip :loll:")
                return
            
            while emoji_url and emoji_url.startswith('alias:'):
                alias = emoji_url[len('alias:'):]
                emoji_url = all_emoji.get(alias)
                
            if not emoji_url:
                client.chat_postMessage(channel=channel_id, thread_ts=ts, text=f"couldn't resolve :{source}: alias :cryin:")
                return
            
            client.reactions_add(channel=channel_id, name='loading', timestamp=ts)
            client.chat_postMessage(channel=channel_id, thread_ts=ts, text="making emoji...")
            
            r = requests.get("https://patpatgifmaker.vercel.app/api/petpet", params={
                    "image_url": emoji_url,
                    "slack_token": os.environ["SLACK_TOKEN"],
                })
            gif_url = r.json()["gif_url"]

            gif = requests.get(gif_url)

            files = {
                "image": ("emoji.gif", gif.content, "image/gif")
            }

            data = {
                "token": os.environ["USER_SLACK_TOKEN"],
                "name": new_name,
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
        
        elif ping_match and not files:
            
            existing = client.api_call("emoji.list")
            if text in existing.get('emoji', {}):
                client.chat_postMessage(channel=channel_id, thread_ts=event.get('ts'), text="emoji with that name already exists :thinkies:")
                client.chat_postMessage(channel=channel_id, thread_ts=event.get('ts'), text="uhh send this again with another name")
                return
            
            else:
                mentioned_user_id = ping_match.group(1)
                emoji_name = fix_emoji_name(ping_match.group(2))
                ts = event.get('ts')

                pfp_url = get_user_pfp(mentioned_user_id)
                if not pfp_url:
                    client.chat_postMessage(channel=channel_id, thread_ts=ts, text="couldn't find their pfp :cryin:")
                    return

                r = requests.get("https://patpatgifmaker.vercel.app/api/petpet", params={
                    "image_url": pfp_url,
                    "slack_token": os.environ["SLACK_TOKEN"],
                })
                gif_url = r.json()["gif_url"]

                gif = requests.get(gif_url)

                files = {
                    "image": ("emoji.gif", gif.content, "image/gif")
                }

                data = {
                    "token": os.environ["USER_SLACK_TOKEN"],
                    "name": emoji_name,
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

                client.chat_postMessage(channel=channel_id, thread_ts=ts, text=f"emoji added :{new_name}:")
                client.reactions_remove(channel=channel_id, name='loading', timestamp=ts)
                client.reactions_add(channel=channel_id, name=new_name, timestamp=ts)

        elif files and text: 
            file = files[0]
            
            existing = client.api_call("emoji.list")
            if text in existing.get('emoji', {}):
                client.chat_postMessage(channel=channel_id, thread_ts=event.get('ts'), text="emoji with that name already exists :thinkies:")
                client.chat_postMessage(channel=channel_id, thread_ts=event.get('ts'), text="uhh send this again with another name")
                return
            
            else:
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
                        "name": fix_emoji_name(text),
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

                    client.chat_postMessage(channel=channel_id, thread_ts=ts, text=f"emoji added :{text}:")
                    client.reactions_remove(channel=channel_id, name='loading', timestamp=ts)
                    client.reactions_add(channel=channel_id, name=text, timestamp=ts)

        elif files and not text:
            ts = event.get('ts')

            client.reactions_add(channel=channel_id, name='wrong', timestamp=ts)
            client.chat_postMessage(channel=channel_id, thread_ts=ts, text="bro send the emoji name atleast :skulk:")
            
        elif text and not files and not ping_match and not emoji_pet_match:
            ts = event.get('ts')
            if "petpheus-version" in text.lower():
                client.chat_postMessage(channel=channel_id, thread_ts=ts, text=f"you are using petpheus {version} :yeah:")

        else:
            return

if __name__ == "__main__":
    app.run(debug=True)