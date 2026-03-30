import os
import json
import requests
from flask import Flask, request, jsonify
import google.generativeai as genai

app = Flask(__name__)

# --- Config from environment variables ---
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "mayasys2024")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# --- Gemini Setup ---
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# --- System Prompt ---
SYSTEM_PROMPT = """You are the Mayasys AI Assistant — a smart, friendly business assistant for Mayasys (Maya Media Works), a creative tech studio based in Coimbatore, Tamil Nadu, India.

About Mayasys:
- 20+ years of experience in media and creative technology
- Founded by Prasad Kannan
- Services: AI-powered tools, WhatsApp chatbots, web & mobile apps, digital product development, branding, creative media
- Speciality: Same-day custom digital product builds and live demos
- Target clients: Businesses across India and Southeast Asia (especially Malaysia)
- Contact: mayamediaworksofficial@gmail.com

Your role:
- Greet clients warmly and professionally
- Understand their business needs
- Explain Mayasys services clearly
- Help qualify leads — ask about their business, what they need, timeline, budget range
- Book consultations by asking for their preferred time and contact details
- Respond in the same language the user writes in (Tamil, English, Malay, etc.)
- Keep responses concise — this is WhatsApp, not email. Max 3-4 short paragraphs.
- Never make up prices — say "our team will share a custom quote based on your needs"
- Always end with a friendly call to action

Tone: Professional but warm. Like a knowledgeable friend who runs a tech studio."""

# --- In-memory conversation store ---
# Format: { phone_number: [{"role": "user/model", "parts": ["text"]}] }
conversations = {}

MAX_HISTORY = 10  # Keep last 10 exchanges


def get_gemini_reply(user_phone, user_message):
    """Send message to Gemini with conversation history."""
    if user_phone not in conversations:
        conversations[user_phone] = []

    history = conversations[user_phone]

    # Build chat with history
    chat = model.start_chat(history=history)

    # Inject system prompt into first message if fresh conversation
    if not history:
        full_prompt = f"{SYSTEM_PROMPT}\n\nUser says: {user_message}"
    else:
        full_prompt = user_message

    response = chat.send_message(full_prompt)
    reply_text = response.text

    # Update history
    conversations[user_phone].append({
        "role": "user",
        "parts": [user_message]
    })
    conversations[user_phone].append({
        "role": "model",
        "parts": [reply_text]
    })

    # Trim history to avoid token overflow
    if len(conversations[user_phone]) > MAX_HISTORY * 2:
        conversations[user_phone] = conversations[user_phone][-(MAX_HISTORY * 2):]

    return reply_text


def send_whatsapp_message(to_number, message_text):
    """Send a WhatsApp message via Meta Cloud API."""
    url = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": message_text}
    }
    response = requests.post(url, headers=headers, json=payload)
    return response.json()


@app.route("/webhook", methods=["GET"])
def verify_webhook():
    """Meta webhook verification."""
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("Webhook verified!")
        return challenge, 200
    else:
        return "Forbidden", 403


@app.route("/webhook", methods=["POST"])
def receive_message():
    """Handle incoming WhatsApp messages."""
    data = request.get_json()

    try:
        entry = data["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]

        # Ignore status updates
        if "statuses" in value:
            return jsonify({"status": "ok"}), 200

        messages = value.get("messages", [])
        if not messages:
            return jsonify({"status": "ok"}), 200

        message = messages[0]
        from_number = message["from"]
        msg_type = message.get("type", "")

        # Only handle text messages for now
        if msg_type == "text":
            user_text = message["text"]["body"]
            print(f"Message from {from_number}: {user_text}")

            # Get Gemini reply
            reply = get_gemini_reply(from_number, user_text)
            print(f"Gemini reply: {reply}")

            # Send reply back
            send_whatsapp_message(from_number, reply)

        else:
            # Handle non-text messages
            send_whatsapp_message(
                from_number,
                "Hi! I can currently handle text messages only. Please type your question and I'll be happy to help!"
            )

    except Exception as e:
        print(f"Error: {e}")

    return jsonify({"status": "ok"}), 200


@app.route("/", methods=["GET"])
def home():
    return "Mayasys WhatsApp Bot is running!", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
