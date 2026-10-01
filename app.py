from flask import Flask, request, jsonify, render_template_string
import requests
import os
import urllib.parse

app = Flask(__name__)

# Get API Key from Environment Variable (Render will set this)
API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

# This is the beautiful Chat Interface (HTML/CSS)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>NexaAI Studio</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #f0f2f5; margin: 0; padding: 0; display: flex; flex-direction: column; height: 100vh; }
        header { background: #4f46e5; color: white; padding: 15px; text-align: center; font-weight: bold; font-size: 1.2rem; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        #chat-box { flex: 1; padding: 20px; overflow-y: scroll; display: flex; flex-direction: column; gap: 15px; }
        .message { max-width: 80%; padding: 12px 16px; border-radius: 18px; font-size: 1rem; line-height: 1.4; word-wrap: break-word; }
        .user { align-self: flex-end; background: #4f46e5; color: white; border-bottom-right-radius: 4px; }
        .bot { align-self: flex-start; background: white; color: #333; border-bottom-left-radius: 4px; box-shadow: 0 1px 2px rgba(0,0,0,0.1); }
        .bot img { max-width: 100%; border-radius: 10px; margin-top: 10px; }
        .input-area { background: white; padding: 15px; display: flex; gap: 10px; border-top: 1px solid #ddd; }
        input { flex: 1; padding: 12px; border: 1px solid #ddd; border-radius: 25px; font-size: 1rem; outline: none; }
        button { background: #4f46e5; color: white; border: none; padding: 0 20px; border-radius: 25px; font-weight: bold; cursor: pointer; }
        button:disabled { background: #ccc; }
    </style>
</head>
<body>
    <header> NexaAI Studio</header>
    
    <div id="chat-box">
        <div class="message bot">Hello! I am NexaAI. Ask me anything, or type <b>image: [description]</b> to generate art!</div>
    </div>

    <div class="input-area">
        <input type="text" id="userInput" placeholder="Type a message..." onkeypress="handleKeyPress(event)">
        <button onclick="sendMessage()" id="sendBtn">Send</button>
    </div>

    <script>
        function handleKeyPress(e) { if (e.key === 'Enter') sendMessage(); }

        function sendMessage() {
            var input = document.getElementById('userInput');
            var text = input.value.trim();
            if (!text) return;

            var chatBox = document.getElementById('chatBox');
            var sendBtn = document.getElementById('sendBtn');
            
            // Add User Message
            chatBox.innerHTML += '<div class="message user">' + text + '</div>';
            input.value = '';
            sendBtn.disabled = true;
            chatBox.scrollTop = chatBox.scrollHeight;

            // Send to Python Backend
            fetch('/chat', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({message: text})
            })
            .then(response => response.json())
            .then(data => {
                // Add Bot Message
                var botMsg = '<div class="message bot">' + data.reply + '</div>';
                chatBox.innerHTML += botMsg;
                sendBtn.disabled = false;
                chatBox.scrollTop = chatBox.scrollHeight;
            })
            .catch(error => {
                chatBox.innerHTML += '<div class="message bot" style="color:red;">Error connecting to AI.</div>';
                sendBtn.disabled = false;
            });
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_message = data.get('message')
    
    # 1. Check for Image Generation Command
    if user_message.lower().startswith('image:'):
        img_prompt = user_message[6:].strip()
        encoded = urllib.parse.quote(img_prompt)
        # Using Pollinations API (Free, No Key)
        img_url = f"https://image.pollinations.ai/prompt/{encoded}?width=512&height=512&nologo=true"
        # Return Markdown image syntax which the browser will render if we parse it, 
        # but for simplicity in this HTML, we return an <img> tag directly.
        return jsonify({"reply": f"Here is your image:<br><img src='{img_url}' alt='AI Image'>"})

    # 2. Text/Code Generation
    if not API_KEY:
        return jsonify({"reply": "⚠️ Server Error: API Key is missing."})

    try:
        res = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost",
                "X-Title": "NexaAI"
            },
            json={
                "model": "cohere/north-mini-code:free",
                "messages": [{"role": "user", "content": user_message}]
            },
            timeout=30
        )
        
        if res.status_code == 200:
            reply = res.json()['choices'][0]['message']['content']
            # Simple formatting for code blocks
            reply = reply.replace("```", "<br><code style='background:#eee; padding:5px; display:block; border-radius:5px;'>").replace("```", "</code><br>")
            reply = reply.replace("\n", "<br>")
            return jsonify({"reply": reply})
        else:
            return jsonify({"reply": f"AI Error: {res.status_code}"})
            
    except Exception as e:
        return jsonify({"reply": f"Connection Error: {e}"})

if __name__ == '__main__':
    # Run the app. Render will override the port with $PORT
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
