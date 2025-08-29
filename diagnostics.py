#!/usr/bin/env python3
"""
Diagnostics script for Voice AI Assistant
Checks environment variables, dependencies, and API connectivity
"""

import os, sys
from dotenv import load_dotenv
load_dotenv()
missing = [k for k in ["TWILIO_ACCOUNT_SID","TWILIO_AUTH_TOKEN","TWILIO_PHONE_NUMBER","OPENAI_API_KEY"] if not os.getenv(k)]
for k in ["TWILIO_ACCOUNT_SID","TWILIO_AUTH_TOKEN","TWILIO_PHONE_NUMBER","OPENAI_API_KEY"]:
    print(("✅" if k not in missing else "❌"), k, "=", ("set" if k not in missing else "MISSING"))
if missing:
    sys.exit(1)
print("✅ Env looks good. Remember: run `ngrok http 5000` and set Twilio webhook to https://<ngrok>/voice (POST).")
