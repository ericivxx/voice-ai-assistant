# Voice AI Assistant

A Flask-based voice AI assistant that integrates with Twilio for voice calls and Together.ai for AI responses.

## Features

- Voice call handling with Twilio
- AI-powered responses using Together.ai's Llama-3 model
- Automatic SMS follow-up after calls
- In-memory call history tracking
- Speech-to-text and text-to-speech conversion

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment variables:**
   Copy `.env.example` to `.env` and fill in your API keys:
   ```
   TWILIO_ACCOUNT_SID=your_twilio_account_sid_here
   TWILIO_AUTH_TOKEN=your_twilio_auth_token_here
   TWILIO_PHONE_NUMBER=your_twilio_phone_number_here
   TOGETHER_API_KEY=your_together_api_key_here
   ```

3. **Run the Flask app:**
   ```bash
   python app.py
   ```

4. **Expose with ngrok (for Twilio webhooks):**
   ```bash
   ngrok http 5000
   ```

5. **Configure Twilio webhook:**
   - Go to Twilio Console > Phone Numbers > Manage > Active Numbers
   - Set Voice webhook to: `https://<ngrok-url>/voice` (HTTP POST)

## Testing Instructions

### Basic Voice Call Test

1. **Call your Twilio number**
   - The system will answer and ask: "Hello, how can I help you today?"

2. **Test AI response**
   - Say something like: "What are your hours?"
   - The AI should respond with a helpful answer via voice
   - You should receive an SMS with the booking form link

3. **Verify functionality**
   - Check that speech is properly transcribed
   - Confirm AI generates relevant responses
   - Ensure SMS is sent to your caller number

### Advanced Testing

#### Test Different Questions
- "What services do you offer?"
- "How can I make an appointment?"
- "What's your cancellation policy?"
- "Do you accept insurance?"

#### Test Edge Cases
- **No speech detected**: Stay silent when prompted
- **Background noise**: Test with ambient sounds
- **Multiple calls**: Make several calls to test call history management

#### Optional: Spam Rejection Test
- Call from a number starting with 1-800 (if you have access)
- Verify the system handles these calls appropriately

### Monitoring

- **Console logs**: Watch for AI response generation and SMS delivery
- **Call history**: Check in-memory storage (resets on app restart)
- **Error handling**: Monitor for API failures or connection issues

### Troubleshooting

- **No AI response**: Check Together.ai API key and model availability
- **SMS not sent**: Verify Twilio credentials and phone number format
- **Speech not detected**: Ensure clear audio and proper microphone setup
- **Webhook errors**: Check ngrok URL and Twilio webhook configuration

## API Endpoints

- `GET /` - Homepage
- `GET /health` - Health check
- `POST /voice` - Initial voice call handler
- `POST /handle_speech` - Speech processing and AI response

## Dependencies

- Flask - Web framework
- Twilio - Voice and SMS services
- Together.ai - AI model API
- python-dotenv - Environment variable management
