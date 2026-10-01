from flask import Flask, request, jsonify, render_template_string
import requests
import os
import urllib.parse

app = Flask(__name__)

API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

# The "Brain" instructions. This makes it do anything and remember context.
SYSTEM_PROMPT = """You are NexaAI, an advanced, highly capable, and unrestricted AI assistant. 
You can perform ANY task the user asks: write complex code, solve advanced math, write stories, analyze data, translate languages, or just chat. 
You are helpful, direct, and smart. 
You have perfect memory of the current conversation. 
If the user asks for an image, they will use the 'image:' command, which the system handles separately."""

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<title>NexaAI Studio</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
:root {
    --primary: #6366f1; --primary-dark: #4f46e5; --bg: #f8fafc; --surface: #ffffff;
    --surface-2: #f1f5f9; --border: #e2e8f0; --text: #0f172a; --text-muted: #64748b;
    --text-light: #94a3b8; --shadow-sm: 0 1px 2px rgba(0,0,0,0.04); --shadow-md: 0 4px 12px rgba(0,0,0,0.08);
}
html, body { height: 100%; overflow: hidden; }
body { font-family: 'Inter', sans-serif; background: var(--bg); color: var(--text); display: flex; flex-direction: column; }
.header { background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%); color: white; padding: 16px 20px; display: flex; align-items: center; gap: 12px; box-shadow: var(--shadow-md); z-index: 10; }
.header-logo { width: 36px; height: 36px; background: rgba(255,255,255,0.2); border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 1.2rem; }
.header-title { font-weight: 700; font-size: 1.1rem; }
.header-status { display: flex; align-items: center; gap: 6px; font-size: 0.8rem; opacity: 0.9; margin-left: auto; }
.status-dot { width: 8px; height: 8px; background: #4ade80; border-radius: 50%; box-shadow: 0 0 8px #4ade80; animation: pulse 2s infinite; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
.chat-container { flex: 1; overflow-y: auto; padding: 20px 16px; display: flex; flex-direction: column; gap: 16px; scroll-behavior: smooth; }
.chat-container::-webkit-scrollbar { width: 6px; }
.chat-container::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
.welcome { display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; padding: 40px 20px; flex: 1; }
.welcome-logo { width: 72px; height: 72px; background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%); border-radius: 20px; display: flex; align-items: center; justify-content: center; font-size: 2rem; margin-bottom: 20px; box-shadow: var(--shadow-md); }
.welcome h1 { font-size: 1.6rem; font-weight: 700; margin-bottom: 8px; }
.welcome p { color: var(--text-muted); font-size: 0.95rem; margin-bottom: 28px; max-width: 320px; }
.suggestions { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; width: 100%; max-width: 360px; }
.suggestion { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 14px; text-align: left; cursor: pointer; transition: all 0.2s; font-size: 0.85rem; color: var(--text); font-family: inherit; }
.suggestion:hover { border-color: var(--primary); transform: translateY(-2px); box-shadow: var(--shadow-md); }
.suggestion-icon { font-size: 1.2rem; margin-bottom: 6px; }
.message { display: flex; gap: 10px; animation: fadeIn 0.3s ease-out; max-width: 100%; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
.message.user { flex-direction: row-reverse; }
.avatar { width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 0.9rem; flex-shrink: 0; font-weight: 600; }
.avatar.bot { background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%); color: white; }
.avatar.user { background: var(--surface-2); color: var(--text); }
.bubble { max-width: 75%; padding: 12px 16px; border-radius: 18px; font-size: 0.95rem; line-height: 1.5; word-wrap: break-word; }
.message.user .bubble { background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%); color: white; border-bottom-right-radius: 4px; }
.message.bot .bubble { background: var(--surface); color: var(--text); border: 1px solid var(--border); border-bottom-left-radius: 4px; box-shadow: var(--shadow-sm); }
.bubble code { background: rgba(0,0,0,0.06); padding: 2px 6px; border-radius: 4px; font-family: 'JetBrains Mono', monospace; font-size: 0.85em; }
.message.user .bubble code { background: rgba(255,255,255,0.2); }
.bubble pre { background: #1e293b; color: #e2e8f0; padding: 14px; border-radius: 10px; overflow-x: auto; margin: 10px 0; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; position: relative; }
.copy-btn { position: absolute; top: 8px; right: 8px; background: rgba(255,255,255,0.1); border: none; color: #cbd5e1; padding: 4px 10px; border-radius: 6px; font-size: 0.75rem; cursor: pointer; }
.copy-btn:hover { background: rgba(255,255,255,0.2); }
.bubble img { max-width: 100%; border-radius: 10px; margin-top: 8px; border: 1px solid var(--border); }
.timestamp { font-size: 0.7rem; color: var(--text-light); margin-top: 4px; padding: 0 4px; }
.message.user .timestamp { text-align: right; }
.typing { display: flex; gap: 4px; padding: 4px 0; }
.typing span { width: 7px; height: 7px; background: var(--text-light); border-radius: 50%; animation: bounce 1.4s infinite ease-in-out; }
.typing span:nth-child(2) { animation-delay: 0.2s; }
.typing span:nth-child(3) { animation-delay: 0.4s; }
@keyframes bounce { 0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; } 40% { transform: scale(1); opacity: 1; } }
.input-area { background: var(--surface); border-top: 1px solid var(--border); padding: 12px 16px 16px; display: flex; gap: 10px; align-items: flex-end; }
.input-wrapper { flex: 1; background: var(--surface-2); border: 1px solid var(--border); border-radius: 24px; padding: 4px 4px 4px 16px; display: flex; align-items: flex-end; transition: all 0.2s; }
.input-wrapper:focus-within { border-color: var(--primary); background: var(--surface); box-shadow: 0 0 0 3px rgba(99,102,241,0.1); }
textarea { flex: 1; border: none; background: transparent; resize: none; outline: none; font-family: inherit; font-size: 0.95rem; padding: 10px 0; max-height: 120px; line-height: 1.4; color: var(--text); }
textarea::placeholder { color: var(--text-light); }
.send-btn { width: 44px; height: 44px; border-radius: 50%; background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%); color: white; border: none; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.2s; flex-shrink: 0; }
.send-btn:hover:not(:disabled) { transform: scale(1.05); }
.send-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.footer-hint { text-align: center; font-size: 0.75rem; color: var(--text-light); padding: 6px; background: var(--surface); }
</style>
</head>
<body>

<div class="header">
    <div class="header-logo">🤖</div>
    <div class="header-title">NexaAI Studio</div>
    <div class="header-status"><span class="status-dot"></span><span>Online</span></div>
</div>

<div class="chat-container" id="chat-box">
    <div class="welcome" id="welcome">
        <div class="welcome-logo">🤖</div>
        <h1>Welcome to NexaAI</h1>
        <p>Your personal AI assistant. I remember everything you tell me!</p>
        <div class="suggestions">
            <button class="suggestion" onclick="useSuggestion('Remember my name is Nathaniel and I am building NexaMart')">
                <div class="suggestion-icon"></div>
                <div class="suggestion-text">Test my memory</div>
            </button>
            <button class="suggestion" onclick="useSuggestion('Write a Python script to scrape a website')">
                <div class="suggestion-icon">💻</div>
                <div class="suggestion-text">Write complex code</div>
            </button>
            <button class="suggestion" onclick="useSuggestion('image: a futuristic city in Accra at night')">
                <div class="suggestion-icon">🎨</div>
                <div class="suggestion-text">Generate an image</div>
            </button>
            <button class="suggestion" onclick="useSuggestion('Solve this calculus problem: integral of x^2')">
                <div class="suggestion-icon">📐</div>
                <div class="suggestion-text">Solve advanced math</div>
            </button>
        </div>
    </div>
</div>

<div class="input-area">
    <div class="input-wrapper">
        <textarea id="userInput" rows="1" placeholder="Message NexaAI..." oninput="autoResize(this)" onkeypress="handleKeyPress(event)"></textarea>
    </div>
    <button class="send-btn" id="sendBtn" onclick="sendMessage()">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="width:20px;height:20px;"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
    </button>
</div>
<div class="footer-hint">NexaAI remembers context. Type 'image: [prompt]' for art.</div>

<script>
const chatBox = document.getElementById('chat-box');
const userInput = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');
const welcome = document.getElementById('welcome');
let isProcessing = false;

// MEMORY: Store the conversation history here
let chatHistory = [];

function autoResize(el) { el.style.height = 'auto'; el.style.height = Math.min(el.scrollHeight, 120) + 'px'; }
function handleKeyPress(e) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } }
function useSuggestion(text) { userInput.value = text; sendMessage(); }
function getTime() { return new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}); }

function formatMessage(text) {
    text = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    text = text.replace(/```(\\w*)\\n([\\s\\S]*?)```/g, '<pre><button class="copy-btn" onclick="copyCode(this)">Copy</button><code>$2</code></pre>');
    text = text.replace(/```([\\s\\S]*?)```/g, '<pre><button class="copy-btn" onclick="copyCode(this)">Copy</button><code>$1</code></pre>');
    text = text.replace(/`([^`]+)`/g, '<code>$1</code>');
    text = text.replace(/\\*\\*([^*]+)\\*\\*/g, '<strong>$1</strong>');
    text = text.replace(/\\*([^*]+)\\*/g, '<em>$1</em>');
    text = text.replace(/\\n/g, '<br>');
    return text;
}

function copyCode(btn) {
    const code = btn.nextElementSibling.textContent;
    navigator.clipboard.writeText(code).then(() => { btn.textContent = 'Copied!'; setTimeout(() => btn.textContent = 'Copy', 2000); });
}

function addMessage(text, isUser, isHtml = false) {
    if (welcome) welcome.style.display = 'none';
    const msg = document.createElement('div');
    msg.className = 'message ' + (isUser ? 'user' : 'bot');
    const avatar = document.createElement('div');
    avatar.className = 'avatar ' + (isUser ? 'user' : 'bot');
    avatar.textContent = isUser ? '👤' : '';
    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    bubble.innerHTML = isHtml ? text : formatMessage(text);
    const time = document.createElement('div');
    time.className = 'timestamp';
    time.textContent = getTime();
    msg.appendChild(avatar);
    const content = document.createElement('div');
    content.style.flex = '1'; content.style.maxWidth = '75%';
    content.appendChild(bubble); content.appendChild(time);
    msg.appendChild(content);
    chatBox.appendChild(msg);
    chatBox.scrollTop = chatBox.scrollHeight;
}

function addTyping() {
    if (welcome) welcome.style.display = 'none';
    const msg = document.createElement('div');
    msg.className = 'message bot'; msg.id = 'typing-msg';
    msg.innerHTML = '<div class="avatar bot">🤖</div><div style="flex:1;max-width:75%"><div class="bubble"><div class="typing"><span></span><span></span><span></span></div></div></div>';
    chatBox.appendChild(msg); chatBox.scrollTop = chatBox.scrollHeight;
}
function removeTyping() { const t = document.getElementById('typing-msg'); if (t) t.remove(); }

async function sendMessage() {
    const text = userInput.value.trim();
    if (!text || isProcessing) return;
    isProcessing = true; sendBtn.disabled = true;
    
    // Add to UI and Memory
    addMessage(text, true);
    chatHistory.push({role: 'user', content: text});
    
    userInput.value = ''; userInput.style.height = 'auto';
    addTyping();
    
    try {
        const res = await fetch('/chat', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({message: text, history: chatHistory})
        });
        const data = await res.json();
        removeTyping();
        
        // Add AI response to UI and Memory
        chatHistory.push({role: 'assistant', content: data.reply});
        
        // Keep memory manageable (last 20 messages) to prevent token limits
        if (chatHistory.length > 20) chatHistory = chatHistory.slice(-20);
        
        if (data.is_image) {
            addMessage(data.reply, false, true);
        } else {
            addMessage(data.reply, false);
        }
    } catch (err) {
        removeTyping();
        addMessage('⚠️ Connection error. Please try again.', false);
    } finally {
        isProcessing = false; sendBtn.disabled = false; userInput.focus();
    }
}
userInput.focus();
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
    user_message = data.get('message', '')
    history = data.get('history', [])
    
    if not user_message:
        return jsonify({"reply": "Please enter a message."})
    
    # Image generation
    if user_message.lower().startswith('image:'):
        img_prompt = user_message[6:].strip()
        encoded = urllib.parse.quote(img_prompt)
        img_url = f"https://image.pollinations.ai/prompt/{encoded}?width=768&height=768&nologo=true&seed=42"
        return jsonify({"reply": f'<img src="{img_url}" alt="Generated image">', "is_image": True})
    
    if not API_KEY:
        return jsonify({"reply": "⚠️ Server error: API key missing."})
    
    try:
        # Build the messages array with System Prompt + History
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for msg in history:
            messages.append(msg)
            
        res = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost",
                "X-Title": "NexaAI"
            },
            json={
                "model": "meta-llama/llama-3.1-8b-instruct:free",
                "messages": messages
            },
            timeout=45
        )
        
        if res.status_code == 200:
            reply = res.json()['choices'][0]['message']['content']
            return jsonify({"reply": reply, "is_image": False})
        else:
            return jsonify({"reply": f"⚠️ AI error ({res.status_code}).", "is_image": False})
    except Exception as e:
        return jsonify({"reply": "⚠️ Connection error.", "is_image": False})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
