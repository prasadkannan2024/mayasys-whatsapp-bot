import os
import json
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "mayasys2024")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

SYSTEM_PROMPT = """You are the Mayasys AI Assistant for Mayasys (Maya Media Works), a creative tech studio in Coimbatore, Tamil Nadu, India. Founded by Prasad Kannan with 20+ years experience. Services: AI tools, WhatsApp bots, web/mobile apps, branding. Contact: mayamediaworksofficial@gmail.com. Be warm, professional, concise. This is WhatsApp - keep replies short. Never quote prices, say team will provide custom quote. Respond in same language as user."""

conversations = {}
MAX_HISTORY = 10

def get_gemini_reply(user_phone, user_message):
    if user_phone not in conversations:
        conversations[user_phone] = []
    history = conversations[user_phone]
    contents = list(history)
    full_text = f"{SYSTEM_PROMPT}\n\nUser: {user_message}" if not history else user_message
    contents.append({"role": "user", "parts": [{"text": full_text}]})
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    response = requests.post(url, headers={"Content-Type": "application/json"}, json={"contents": contents, "generationConfig": {"temperature": 0.7, "maxOutputTokens": 500}}, timeout=30)
    result = response.json()
    reply_text = result["candidates"][0]["content"]["parts"][0]["text"]
    conversations[user_phone].append({"role": "user", "parts": [{"text": user_message}]})
    conversations[user_phone].append({"role": "model", "parts": [{"text": reply_text}]})
    if len(conversations[user_phone]) > MAX_HISTORY * 2:
        conversations[user_phone] = conversations[user_phone][-(MAX_HISTORY * 2):]
    return reply_text

def send_whatsapp_message(to_number, message_text):
    url = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": to_number, "type": "text", "text": {"body": message_text}}
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    print(f"WA send: {response.json()}")
    return response.json()

@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("Webhook verified!")
        return challenge, 200
    return "Forbidden", 403

@app.route("/webhook", methods=["POST"])
def receive_message():
    data = request.get_json()
    print(f"Incoming: {json.dumps(data)}")
    try:
        entry = data["entry"][0]
        value = entry["changes"][0]["value"]
        if "statuses" in value:
            return jsonify({"status": "ok"}), 200
        messages = value.get("messages", [])
        if not messages:
            return jsonify({"status": "ok"}), 200
        message = messages[0]
        from_number = message["from"]
        if message.get("type") == "text":
            user_text = message["text"]["body"]
            print(f"From {from_number}: {user_text}")
            reply = get_gemini_reply(from_number, user_text)
            print(f"Reply: {reply}")
            send_whatsapp_message(from_number, reply)
        else:
            send_whatsapp_message(from_number, "Hi! Please send a text message and I will be happy to help!")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    return jsonify({"status": "ok"}), 200

@app.route("/", methods=["GET"])
def home():
    return "Mayasys WhatsApp Bot is running!", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
