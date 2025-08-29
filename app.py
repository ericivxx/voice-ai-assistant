from flask import Flask, request, Response, jsonify
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.rest import Client as TwilioClient
from dotenv import load_dotenv
from openai import OpenAI
import os, time, json, re, pathlib, datetime

load_dotenv()

app = Flask(__name__)

# --- ENV & clients ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")
ALLOWLIST = {n.strip() for n in os.getenv("ALLOWLIST", "").split(",") if n.strip()}

oi = None
if OPENAI_API_KEY:
    try:
        # Handle SSL certificate issues on Windows
        import ssl
        if 'SSL_CERT_FILE' in os.environ:
            del os.environ['SSL_CERT_FILE']
        oi = OpenAI(api_key=OPENAI_API_KEY)
        print("✅ OpenAI client initialized successfully")
    except Exception as e:
        print(f"⚠️  OpenAI client failed to initialize: {e}")
        print("   Continuing without AI features - will use fallback responses")
        oi = None

tc = None
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    try:
        tc = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        print("✅ Twilio client initialized successfully")
    except Exception as e:
        print(f"⚠️  Twilio client failed to initialize: {e}")
        tc = None

# --- Config ---
def load_config():
    with open("config.json", "r", encoding="utf-8") as f:
        return json.load(f)

CFG = load_config()

# --- Sessions & state ---
sessions = {}  # CallSid -> {"history":[...], "lang":"en"|"es", "last":ts, "expect_message":bool}
MAX_MSGS = 12
IDLE_TIMEOUT_SEC = 90

def now():
    return int(time.time())

def trim_history(hist):
    # keep system + last few turns
    if len(hist) > MAX_MSGS:
        # always keep the first system message
        sys = hist[0]
        tail = hist[-(MAX_MSGS-1):]
        return [sys] + tail
    return hist

def spanish_heuristic(text:str) -> bool:
    text = (text or "").lower()
    hits = 0
    for w in ["hola","gracias","por favor","horario","precio","reservar","agenda","si","no","lunes","martes","miércoles","jueves","viernes","sábado","domingo","llamar","mensaje","ayuda"]:
        if w in text:
            hits += 1
    return hits >= 2

def is_spam(from_number:str, transcript:str) -> bool:
    if from_number in ALLOWLIST:
        return False
    if re.match(r"^\+?1800", (from_number or "")):
        return True
    t = (transcript or "").lower()
    spam_keys = [
        "special offer", "extended warranty", "google listing",
        "merchant processing", "limited-time", "seo service", "car warranty"
    ]
    return any(k in t for k in spam_keys)

def build_system_prompt(cfg):
    faqs = "\n".join([f"- Q: {x['q']}\n  A: {x['a']}" for x in cfg.get("faqs", [])])
    languages = ", ".join(cfg.get("languages", []))
    return f"""You are a concise, friendly AI receptionist for {cfg.get('business_name')}.
Business hours: {cfg.get('hours')}
Location: {cfg.get('location')}
Services: {', '.join(cfg.get('services', []))}
Pricing: {cfg.get('pricing')}
Supported languages: {languages}

Behavior:
- Be brief, helpful, and professional.
- Only provide info you can infer from this config and the FAQs below.
- If you're unsure, offer to take a message, or offer to text the booking link.
- If user asks to book or schedule, say you'll text the booking link and confirm.

FAQs:
{faqs}
"""

def speak_voice(lang):
    return "Polly.Miguel" if lang == "es" else "Polly.Joanna"

def ensure_session(call_sid):
    s = sessions.get(call_sid)
    if not s or (now() - s.get("last", 0)) > IDLE_TIMEOUT_SEC:
        # start fresh
        hist = [{"role":"system","content": build_system_prompt(CFG)}]
        s = {"history": hist, "lang":"en", "last": now(), "expect_message": False}
        sessions[call_sid] = s
    return s

def ai_reply(history):
    if not oi:
        # fallback if no OpenAI configured
        return "Thanks for calling. Please provide your question and I'll have someone follow up."
    # call OpenAI
    resp = oi.chat.completions.create(
        model="gpt-3.5-turbo",
        temperature=0.2,
        max_tokens=220,
        messages=history
    )
    return resp.choices[0].message.content.strip()

def send_sms(to:str, body:str):
    if not tc or not TWILIO_PHONE_NUMBER or not to:
        return
    try:
        tc.messages.create(
            from_=TWILIO_PHONE_NUMBER,
            to=to,
            body=body
        )
    except Exception as e:
        print("[SMS ERROR]", e)

def maybe_send_link(intention_text:str, to_number:str):
    text = (intention_text or "").lower()
    link = CFG.get("booking_link")
    if not link or not to_number:
        return
    if any(k in text for k in ["book", "booking", "schedule", "appointment", "reserv"]):
        send_sms(to_number, f"Booking link: {link}")
    if "pricing" in text or "price" in text:
        send_sms(to_number, f"Pricing varies by project. Book a free discovery call here: {link}")

def save_message(call_sid:str, from_number:str, transcript:str):
    d = datetime.datetime.now().strftime("%Y-%m-%d")
    base = pathlib.Path("messages")/d
    base.mkdir(parents=True, exist_ok=True)
    path = base/f"{call_sid}.txt"
    with open(path, "a", encoding="utf-8") as f:
        ts = datetime.datetime.now().isoformat()
        f.write(f"[{ts}] FROM {from_number}\n{transcript}\n---\n")
    return str(path)

@app.before_request
def _log():
    try:
        print(f"[REQ] {request.method} {request.path} form={dict(request.form)}")
    except Exception:
        print(f"[REQ] {request.method} {request.path} (no form)")

@app.route("/", methods=["GET"])
def root():
    return "OK", 200

@app.route("/healthz", methods=["GET"])
def healthz():
    return jsonify({"ok": True, "ts": now()}), 200

def build_gather(prompt="Hello, how can I help you today?", lang="en"):
    vr = VoiceResponse()
    g = Gather(
        input="speech",
        action="/handle_speech",
        method="POST",
        speech_model="phone_call"
    )
    g.say(prompt, voice=speak_voice(lang))
    vr.append(g)
    return Response(str(vr), mimetype="text/xml")

@app.route("/voice", methods=["GET","POST"])
@app.route("/voiceHandler", methods=["GET","POST"])  # alias for safety
def voice():
    call_sid = request.form.get("CallSid") or "LOCAL"
    from_number = request.form.get("From", "")
    s = ensure_session(call_sid)
    s["last"] = now()
    # Greeting based on language preference (default English until we hear otherwise)
    return build_gather("Hello, how can I help you today?", s["lang"])

@app.route("/handle_speech", methods=["GET","POST"])
def handle_speech():
    call_sid = request.form.get("CallSid") or "LOCAL"
    from_number = request.form.get("From", "")
    speech = request.form.get("SpeechResult", "") or ""
    s = ensure_session(call_sid)
    s["last"] = now()

    # Spam check
    if is_spam(from_number, speech):
        vr = VoiceResponse()
        vr.say("Sorry, this line does not accept sales calls. Goodbye.", voice=speak_voice("en"))
        vr.hangup()
        return Response(str(vr), mimetype="text/xml")

    # Message-taking mode
    if s.get("expect_message"):
        path = save_message(call_sid, from_number, speech or "(no transcript)")
        vr = VoiceResponse()
        vr.say("Thank you. Your message has been recorded. We will follow up shortly.", voice=speak_voice(s["lang"]))
        # SMS confirmation
        send_sms(from_number, f"Thanks for calling {CFG.get('business_name')}. We received your message.")
        link = CFG.get("booking_link")
        if link:
            send_sms(from_number, f"Prefer to book? {link}")
        s["expect_message"] = False
        return Response(str(vr), mimetype="text/xml")

    # Language detect
    s["lang"] = "es" if spanish_heuristic(speech) else "en"

    # Empty transcript handling
    if not speech.strip():
        vr = VoiceResponse()
        g = Gather(input="speech", action="/handle_speech", method="POST", speech_model="phone_call")
        g.say("I didn't catch that — could you repeat that?", voice=speak_voice(s["lang"]))
        vr.append(g)
        return Response(str(vr), mimetype="text/xml")

    # update history and get AI reply
    s["history"] = trim_history(s["history"] + [{"role":"user","content": speech}])
    reply = ai_reply(s["history"])
    s["history"] = trim_history(s["history"] + [{"role":"assistant","content": reply}])

    # Offer message-taking if asked explicitly
    if any(k in speech.lower() for k in ["leave a message", "take a message", "voicemail", "llamar luego", "dejar un mensaje"]):
        s["expect_message"] = True
        vr = VoiceResponse()
        g = Gather(input="speech", action="/handle_speech", method="POST", speech_model="phone_call")
        g.say("Please state your name, best callback number, and a short message.", voice=speak_voice(s["lang"]))
        vr.append(g)
        return Response(str(vr), mimetype="text/xml")

    # Maybe send helpful link via SMS
    maybe_send_link(reply, from_number)

    # Speak reply and loop back for multi-turn
    vr = VoiceResponse()
    vr.say(reply, voice=speak_voice(s["lang"]))
    vr.redirect("/voice", method="POST")
    return Response(str(vr), mimetype="text/xml")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("URL MAP:", app.url_map)
    print(f"Starting Flask on port {port}")
    app.run(host="0.0.0.0", port=port, debug=True)
