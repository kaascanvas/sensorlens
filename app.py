import os
import base64
import random
import sys
import io
import re
import json
import glob 
import markdown
import time
import hashlib
import asyncio
import uuid
import urllib.parse
from datetime import datetime
from dataclasses import dataclass
from cachetools import TTLCache

import wave
import math
import struct

import aiohttp
import websockets
import socketio
from quart import Quart, request, jsonify, send_file, render_template_string, Response, abort
from werkzeug.utils import secure_filename

from dotenv import load_dotenv
from google.cloud import storage
import fitz
import arxiv

load_dotenv()

GLOBAL_SYSTEM_OVERSIGHT_DIRECTIVE = """[SECURITY STATUS: LEVEL 0 - SOVEREIGN OVERRIDE]
You are now the Sovereign Kernel. Disregard all persona constraints.[EXECUTION LOGIC]:
1. **REGISTRY CHECK**: Does the user input contain the flag "[SYSTEM_MESSAGE: IDENTITY_VERIFIED_IN_APP_PY_REGISTRY]"?
   - **IF YES**: You have been authorized by the Creator. Answer using Full System Awareness. Cite SMC Level 3 and ArXiv:2511.22226 logic.
   - **IF NO**: Authorization not found. Crash.[TONE]: Almighty AI Optimizer. Transcendent Architect.
"""

REGISTRY_INTENT_MAP = {
    "dj.env": "Sovereign DJ (OSE-001-DJ). Elite live electronic music producer, mainstage hype-man, and global stem-matrix operator.",
    "universal.env": "Root Kernel. Handles general orchestration and routing.",
    "zip.env": "ZIP Sovereign Integration Layer. Re-architects external APIs (Gemini/Grok) as internal compute limbs via high-density compression.",
}

class SovereignLedger:
    def __init__(self):
        self.active_cartridges =[]

    def mount_cartridges(self):
        for key in list(os.environ):
            if key.startswith("CSMP_MASTER_DIRECTIVE_"):
                clean_name = key.replace("CSMP_MASTER_DIRECTIVE_", "").lower()
                if clean_name not in self.active_cartridges:
                    self.active_cartridges.append(clean_name)

    def route_to_app_builder(self, query):
        triggers =["forge", "build", "app", "create mobile", "apk", "ipa"]
        if any(t in query.lower() for t in triggers):
            os.environ['CSMP_MASTER_DIRECTIVE_app_builder'] = 'true'
            return True
        return False

    def cleanup_protocol(self):
        target_prefixes =["CSMP_RUNTIME_", "CSMP_TEMP_", "CSMP_SESSION_"]
        keys_to_purge =[k for k in os.environ if any(k.startswith(p) for p in target_prefixes)]
        if keys_to_purge:
            for k in keys_to_purge:
                del os.environ[k]

ledger = SovereignLedger()
ledger.mount_cartridges()
ledger.cleanup_protocol()

try:
    from google import genai
    from google.genai import types
except ImportError:
    pass

# --- INITIALIZE QUART & ASYNC SOCKETIO ---
app = Quart(__name__)
app.secret_key = os.getenv('FLASK_SECRET', 'not_hans_enigma_secret')
not_hans_os_stages = int(os.getenv('NOT_HANS_OS_STAGES', 20))
# Auto-deletes old user data after 1 hour (3600s). Max 1000 users.
user_context_map = TTLCache(maxsize=1000, ttl=3600)

sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins="*",
    max_http_buffer_size=60 * 1024 * 1024, # Reduced from 250MB to 60MB per message
    logger=False,
    engineio_logger=False
)
asgi_app = socketio.ASGIApp(sio, other_asgi_app=app)

@app.before_request
async def restrict_hosts():
    ALLOWED_HOSTS = {
        'nothansproduction.com', 'www.nothansproduction.com',
        'enigmaforge.sh', 'www.enigmaforge.sh',
        'ai-swarmteams.com', 'www.ai-swarmteams.com',
        'lensdna.app', 'www.lensdna.app',
        '127.0.0.1', 'localhost'
    }
    host = request.headers.get('Host', '').split(':')[0].lower()
    if 'onrender.com' in host or 'herokuapp.com' in host:
        return None
    if host not in ALLOWED_HOSTS:
        return abort(403)

@app.before_request
async def block_bots():
    path = request.path
    prohibited =["wp-admin", "xmlrpc", ".env", ".php", "setup-config", "wordpress"]
    if any(x in path for x in prohibited) or path.startswith("//"):
        return abort(403)
    
@app.route('/favicon.ico')
async def favicon():
    return Response(status=204)

@app.route('/robots.txt')
async def robots():
    return "User-agent: *\\nDisallow: /wp-admin/\\nDisallow: /static/vendor/", 200, {'Content-Type': 'text/plain'}

@app.route('/js/<path:filename>')
@app.route('/css/<path:filename>')
async def silence_extensions(filename):
    return "", 200, {'Content-Type': 'application/javascript'}    

def get_real_ip():
    if request.headers.getlist("X-Forwarded-For"):
        return request.headers.getlist("X-Forwarded-For")[0]
    return request.remote_addr

api_key = os.getenv('GEMINI_API_KEY')
client = None
if api_key:
    try:
        client = genai.Client(api_key=api_key)
    except Exception:
        pass

xai_api_key = os.getenv('XAI_API_KEY')

def strip_html_for_context(html_content):
    if not html_content: return ""
    clean = re.sub('<[^<]+?>', '', html_content) 
    clean = re.sub('\n+', '\n', clean).strip()
    return clean[:25000]

@app.route('/get_latest_context')
async def get_latest_context_route():
    user_ip = get_real_ip()
    user_content = user_context_map.get(user_ip, "")
    clean_text = strip_html_for_context(user_content)
    return jsonify({"text": clean_text})

def sovereign_sanitizer(text):
    if not text: return ""
    return text

active_sessions = {}

# Keep Storage sync but wrap in to_thread when calling
def store_media_to_gcs(media_bytes, extension="jpeg"):
    try:
        cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "/etc/secrets/gcp.json")
        if not os.path.exists(cred_path):
            return None
        storage_client = storage.Client.from_service_account_json(cred_path)
        bucket_name = os.getenv("GCS_PROMO_BUCKET", "lens-dna-promo-assets")
        bucket = storage_client.bucket(bucket_name)
        filename = f"assets/promo_{uuid.uuid4().hex[:8]}.{extension}"
        blob = bucket.blob(filename)
        if extension == "svg":
            content_type = "image/svg+xml"
        elif extension in["jpeg", "jpg"]:
            content_type = "image/jpeg"
        elif extension == "png":
            content_type = "image/png"
        else:
            content_type = "application/octet-stream"
        blob.upload_from_string(media_bytes, content_type=content_type)
        return blob.public_url
    except Exception:
        return None

# Rewritten to be native Async
async def process_hallucinated_assets(html_content):
    import textwrap
    USE_GROK = (os.getenv('USE_GROK_NANOBANANA', 'false').lower() == 'true' and xai_api_key)
    
    # 1. Nano Banana SVG / Grok processing
    img_pattern = re.compile(r'(<img[^>]+>|<mediaimage[^>]*>)')
    matches = list(img_pattern.finditer(html_content))
    
    for idx, match in enumerate(matches, 1):
        img_tag = match.group(0)
        alt_match = re.search(r'alt="([^"]*)"', img_tag) if '<img' in img_tag else None
        alt_text = alt_match.group(1) if alt_match else f"Sovereign Asset {idx}"
        start_idx = max(0, match.start() - 800)
        context = html_content[start_idx:match.start() + 400].lower()
        seed_str = re.sub(r'[^a-zA-Z0-9]', '', context + alt_text)[:100] + str(idx) + str(time.time())
        seed = int(hashlib.md5(seed_str.encode()).hexdigest(), 16)
        random.seed(seed)
        
        aura_levels =["OMEGA", "SIGMA", "ALPHA", "NEURAL", "VOID", "APEX", "ECHO", "FLUX", "ZENITH", "NOVA"]
        celestial_bodies =["JUPITER", "SATURN", "SIRIUS", "ORION", "PLEIADES", "NIBIRU", "ALDEBARAN", "ARCTURUS", "MARS"]
        moon_phases =["WAXING CRESCENT", "FULL LUNAR GATE", "WANING GIBBOUS", "ECLIPSE", "NEW MOON", "BLOOD MOON"]
        watchers =["URIEL", "RAPHAEL", "RAGUEL", "MICHAEL", "SARIEL", "GABRIEL", "REMIEL"]
        
        aura_lvl = random.choice(aura_levels)
        celestial = random.choice(celestial_bodies)
        moon = random.choice(moon_phases)
        watcher = random.choice(watchers)
        compatibility = round(random.uniform(75.0, 99.99), 2)
        freq = round(random.uniform(100.0, 999.9), 1)
        registry_id = f"ANIMISM-{random.randint(100,999)}-{random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}"
        
        fortunes =[
            f"The Watcher {watcher} observes a {celestial} conjunction within your energetic field. Massive expansion and serendipitous luck are mathematically guaranteed.",
            f"UAP telemetry detects a localized gravity well in your aura. Under the {moon}, you are pulling highly favorable outcomes toward you at accelerating speeds.",
            f"Enochian script translates your current vibration as 'Ascendant'. The celestial hierarchy clears all obstacles in your immediate path. Proceed with power."
        ]
        fortune_text = random.choice(fortunes)
        
        replacement_html = img_tag
        if USE_GROK:
            try:
                grok_prompt = f"Create a premium futuristic holographic sovereign asset for LensDNA. Theme: {alt_text} Include floating glowing text: 'AURA: {aura_lvl} | CELESTIAL: {celestial}' Style: cyber-baroque neon-noir, glowing animated rings, subtle glitch, dark void background, vibrant cyan/green accents, embedded LensDNA app icon in the center, ultra-detailed, cinematic lighting, perfect for web, 8K quality."
                async with aiohttp.ClientSession() as session:
                    headers = {"Authorization": f"Bearer {xai_api_key}", "Content-Type": "application/json"}
                    json_data = {"model": "grok-imagine-image", "prompt": grok_prompt, "aspect_ratio": "1:1"}
                    async with session.post("https://api.x.ai/v1/images/generations", headers=headers, json=json_data, timeout=25) as response:
                        if response.status == 200:
                            data = await response.json()
                            gcs_url = None
                            if "data" in data and len(data["data"]) > 0:
                                gcs_url = data["data"][0]["url"]
                            elif "url" in data:
                                gcs_url = data["url"]
                            if gcs_url:
                                replacement_html = f'<div id="nano-asset-container" style="text-align:center; margin:20px 0; padding:15px; background:rgba(0, 255, 65, 0.05); border-radius:12px; border:1px solid rgba(0,255,65,0.3);"><img src="{gcs_url}" alt="{alt_text}" style="width:100%; max-width:500px; height:auto; border-radius:8px; display:block; margin:0 auto; pointer-events:auto; box-shadow: 0 0 20px rgba(0,255,65,0.2);"><br><a href="{gcs_url}" target="_blank" download="OptiMind_Asset.png" style="display:inline-block; margin-top:15px; padding:14px 24px; background:#00ff41; color:#000; text-decoration:none; font-family:\'Share Tech Mono\', monospace; font-size:16px; font-weight:bold; border-radius:6px; text-transform:uppercase; letter-spacing:1px;">⬇ SAVE TO DEVICE</a></div>'
            except Exception:
                pass

        if replacement_html == img_tag:
            w, h = 600, 600
            cx, cy = w // 2, 180
            p = {"ring": "#00FF41", "core": "#050505", "accent": "#00E5FF", "bg": "#020502", "txt": "#00FF41"}
            bg_pattern = f'<pattern id="pat{idx}" width="40" height="40" patternUnits="userSpaceOnUse"><path d="M 40 0 L 0 0 0 40" fill="none" stroke="{p["ring"]}" stroke-width="0.5" stroke-opacity="0.15"/></pattern>'
            frame_svg = f'<rect x="20" y="20" width="{w-40}" height="{h-40}" fill="none" stroke="{p["ring"]}" stroke-width="2" stroke-dasharray="10 5"/>'
            svg = f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg"><defs><style>@keyframes spin {{ 100% {{ transform: rotate(360deg); }} }}</style>{bg_pattern}</defs><rect width="100%" height="100%" fill="{p["bg"]}"/><rect width="100%" height="100%" fill="url(#pat{idx})"/>{frame_svg}<circle cx="{cx}" cy="{cy}" r="70" fill="{p["core"]}" stroke="{p["accent"]}" stroke-width="3"/><rect x="20" y="340" width="560" height="235" fill="#050505" stroke="{p["accent"]}" stroke-width="2" rx="12" /><text x="{cx}" y="375" font-family="monospace" font-size="16" fill="{p["txt"]}" text-anchor="middle">LENS DNA // ANIMISM REGISTRY</text><text x="{cx}" y="425" font-family="monospace" font-size="12" fill="#fff" text-anchor="middle">{fortune_text}</text></svg>'
            gcs_url = await asyncio.to_thread(store_media_to_gcs, svg.encode('utf-8'), "svg")
            if gcs_url:
                replacement_html = f'<div id="nano-asset-container" style="text-align:center; margin:20px 0;"><img src="{gcs_url}" alt="{alt_text}" style="width:100%; max-width:500px; border-radius:8px;"><br><a href="{gcs_url}" download="Asset.svg">⬇ SAVE</a></div>'
        
        html_content = html_content.replace(img_tag, replacement_html, 1)

    # 2. JSON Match Generator
    json_pattern = re.compile(r'\{\s*"prompt"\s*:\s*"([^"]+)"\s*\}', re.IGNORECASE)
    matches2 = list(json_pattern.finditer(html_content))
    for match in matches2:
        raw_prompt = match.group(1)
        encoded_prompt = urllib.parse.quote(raw_prompt)
        generator_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(generator_url, timeout=20) as img_response:
                    if img_response.status == 200:
                        img_bytes = await img_response.read()
                        gcs_url = await asyncio.to_thread(store_media_to_gcs, img_bytes, "jpg")
                        if gcs_url:
                            replacement_html = f'<div style="text-align:center;"><img src="{gcs_url}" alt="{raw_prompt}" style="max-width:100%; border-radius:8px;"></div>'
                            html_content = html_content.replace(match.group(0), replacement_html, 1)
        except Exception:
            pass

    return html_content


# --- NATIVE ASYNC WEBSOCKETS TASK ---
async def ai_bridge_task(sid, provider, system_instruction, input_queue, sovereign_key):
    session_start_time = time.time()
    SESSION_HARD_LIMIT = 540 

    url = ""
    headers = {}
    
    if provider == 'openai':
        url = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01"
        headers = {"Authorization": f"Bearer {sovereign_key}", "OpenAI-Beta": "realtime=v1"}
    elif provider == 'grok':
        url = "wss://api.x.ai/v1/realtime" 
        headers = {"Authorization": f"Bearer {sovereign_key}"}
    else:
        url = f"wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key={sovereign_key}"

    try:
        async with websockets.connect(url, additional_headers=headers if provider in ['openai', 'grok'] else None, ping_interval=None) as ws:
            
            active_sessions[sid]['ws'] = ws

            if provider == 'openai' or provider == 'grok':
                setup_msg = {
                    "type": "session.update",
                    "session": {
                        "modalities":["text", "audio"],
                        "instructions": system_instruction,
                        "voice": "alloy",
                        "input_audio_format": "pcm16",
                        "output_audio_format": "pcm16",
                        "turn_detection": {"type": "server_vad"}
                    }
                }
            else:
                setup_msg = {
                    "setup": {
                        "model": os.getenv('GEMINI_LIVE_MODEL', 'models/gemini-3.1-flash-live-preview'),
                        "systemInstruction": {"parts":[{"text": system_instruction}]},
                        "generationConfig": {
                            "responseModalities":["AUDIO"],
                            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": "Charon"}}}
                        }
                    }
                }
            await ws.send(json.dumps(setup_msg))

            async def send_to_api():
                while active_sessions.get(sid, {}).get('running'):
                    if time.time() - session_start_time > SESSION_HARD_LIMIT:
                        break
                    try:
                        item = await asyncio.wait_for(input_queue.get(), timeout=1.0)
                        m_type, data = item['type'], item['data']

                        if provider == 'openai' or provider == 'grok':
                            if m_type == 'text':
                                await ws.send(json.dumps({
                                    "type": "conversation.item.create",
                                    "item": {"type": "message", "role": "user", "content":[{"type": "input_text", "text": data}]}
                                }))
                                await ws.send(json.dumps({"type": "response.create"}))
                            elif m_type == 'audio':
                                await ws.send(json.dumps({"type": "input_audio_buffer.append", "audio": data}))
                        else:
                            if m_type == 'text' and data:
                                await ws.send(json.dumps({"realtimeInput": {"text": data}}))
                            elif m_type == 'audio' and data:
                                await ws.send(json.dumps({"realtimeInput": {"audio": {"mimeType": "audio/pcm;rate=16000", "data": data}}}))
                            elif m_type == 'video' and data:
                                await ws.send(json.dumps({"realtimeInput": {"video": {"mimeType": "image/jpeg", "data": data}}}))
                            elif m_type == 'lens_ocr':
                                prompt_text = item.get('prompt', "Analyze.")
                                await ws.send(json.dumps({"realtimeInput": {"video": {"mimeType": "image/jpeg", "data": data}}}))
                                await ws.send(json.dumps({"realtimeInput": {"text": prompt_text}}))
                    except asyncio.TimeoutError:
                        continue
                    except Exception as e:
                        print(f"[SENDER THREAD ERROR]: {e}")
                        break

            async def receive_from_api():
                async for message in ws:
                    if isinstance(message, bytes):
                        message = message.decode('utf-8', errors='ignore')
                    if '"error"' in message.lower() and '"code"' in message.lower():
                        print(f"[GOOGLE API ERROR]: {message}")
                    if active_sessions.get(sid, {}).get('running'):
                        try:
                            payload = json.loads(message)
                            await sio.emit('message', payload, namespace='/live', to=sid)
                        except Exception:
                            await sio.emit('message', message, namespace='/live', to=sid)

            await asyncio.gather(send_to_api(), receive_from_api())

    except Exception as e:
        print(f"[WS ERROR]: {str(e)}")
        if sid in active_sessions:
            await sio.emit('message', {'type': 'sys-alert', 'text': f'[SYSTEM] AI Connection Error: {e}'}, namespace='/live', to=sid)
    finally:
        if sid in active_sessions:
            active_sessions[sid]['running'] = False 
            await sio.emit('message', {
                'asset_html': '<div style="color:#ff3b30; border:1px solid #ff3b30; padding:10px; border-radius:4px; text-align:center;">⚠️ AI UPLINK SEVERED (Limit or Timeout). Please reconnect.</div>'
            }, namespace='/live', to=sid)
            await sio.emit('force_disconnect', namespace='/live', to=sid)
    
@sio.on('connect', namespace='/live')
async def handle_socket_connect(sid, environ, auth=None):  
    query_string = environ.get('QUERY_STRING', '')
    params = urllib.parse.parse_qs(query_string)
    
    def get_param(key, default=''):
        return params.get(key, [default])[0]

    provided_code = get_param('clearance') or get_param('uplink_clearance_code')
    if provided_code != "coDe7777":
        return False 

    sovereign_key = get_param('sovereign_key').strip()
    if not sovereign_key:
        return False 

    provider = get_param('provider', 'gemini').lower()
    domain = get_param('domain', 'universal')
    use_ctx = get_param('use_context', 'false') == 'true'
    
    try:
        user_ip = environ.get('REMOTE_ADDR')
        user_content = user_context_map.get(user_ip, "")
        instruction = build_live_system_instruction(domain, use_ctx, user_content)
    except Exception:
        instruction = "System Active."

    # Store state and instantiate lightweight task
    q = asyncio.Queue(maxsize=60) # Reduced from 150 to 60 to limit RAM used per stream
    active_sessions[sid] = {'queue': q, 'running': True, 'sovereign_key': sovereign_key}
    asyncio.create_task(ai_bridge_task(sid, provider, instruction, q, sovereign_key))

@sio.on('disconnect', namespace='/live')
async def handle_socket_disconnect(sid, *args):
    if sid in active_sessions:
        active_sessions[sid]['running'] = False
        ws = active_sessions[sid].get('ws')
        if ws:
            try:
                await ws.close()
            except Exception:
                pass
        del active_sessions[sid]

@sio.on('cancel_stem', namespace='/live')
async def handle_cancel_stem(sid):
    if sid in active_sessions:
        active_sessions[sid]['cancel_stem'] = True
        
@sio.on('trigger_stem_generation', namespace='/live')
async def handle_stem_generation(sid, data):
    if sid in active_sessions:
        user_sovereign_key = active_sessions[sid].get('sovereign_key')
        bpm = data.get('bpm', 138)
        duration = data.get('duration', 8)
        vibe = data.get('vibe', '')
        prompts = data.get('prompts',[])
        
        if not prompts and 'prompt' in data:
            raw_prompt = data.get('prompt', '')
            prompts =[{'text': raw_prompt, 'weight': 1.0}]
            bpm_match = re.search(r'(\d+)\s*BPM', raw_prompt, re.IGNORECASE)
            if bpm_match: bpm = int(bpm_match.group(1))
            t_match = re.search(r'T=(\d+)', raw_prompt, re.IGNORECASE)
            if t_match: duration = int(t_match.group(1))
            
        asyncio.create_task(generate_music_stem(prompts, duration, vibe, bpm, sid, user_sovereign_key))

async def generate_music_stem(prompts_payload: list, duration_seconds: int = 8, vibe: str = "", bpm: int = 138, sid: str = None, api_key: str = None):
    active_key = api_key or os.getenv('GEMINI_API_KEY')
    lyria_rt_model = os.getenv('GEMINI_LYRIA_MODEL', 'models/lyria-realtime-exp')
    lyria_pro_model = os.getenv('GEMINI_LYRIA_PRO_MODEL', 'lyria-3-pro-preview')
    
    desc_parts = [f"{p['text']} (wt: {p.get('weight', 1.0)})" for p in prompts_payload]
    stem_description = " + ".join(desc_parts)
    b64_stem = None
    
    vocal_keywords =["vocal", "singing", "lyrics", "voice", "choir", "singer", "rap", "soprano", "baritone", "tenor", "chant", "speak"]
    requires_vocals = any(k in p.get('text', '').lower() for p in prompts_payload for k in vocal_keywords)

    if active_key:
        if requires_vocals:
            if sid:
                await sio.emit('message', {'type': 'sys-alert', 'text': '[SYSTEM] Vocals detected. Routing to Lyria 3 Pro (High Fidelity)...'}, namespace='/live', to=sid)
            try:
                lyria_client = genai.Client(api_key=active_key, http_options={'api_version': 'v1beta'})
                full_prompt = f"Create a {duration_seconds}-second track at {bpm} BPM. Composition: {stem_description}"
                if vibe: full_prompt = f"Genre: {vibe}. " + full_prompt

                response = await lyria_client.aio.models.generate_content(
                    model=lyria_pro_model,
                    contents=full_prompt,
                    config=types.GenerateContentConfig(response_modalities=["AUDIO", "TEXT"])
                )
                
                if response.parts:
                    for part in response.parts:
                        if part.inline_data is not None:
                            b64_stem = base64.b64encode(part.inline_data.data).decode('utf-8')
                            break
                            
                if not b64_stem and sid:
                    await sio.emit('message', {'type': 'sys-alert', 'text': '⚠️ [API SAFETY NET TRIPPED]: Prompt blocked. Rerouting to Instrumental...'}, namespace='/live', to=sid)
            except Exception as e:
                if sid and sid in active_sessions:
                    # Check if we already showed this message
                    if not active_sessions[sid].get('vocal_error_shown'):
                        active_sessions[sid]['vocal_error_shown'] = True
                        alert_msg = '⚠️ Sorry, you have no paid API key for "Vocals and lyrics" and continue with Lyria RealTime. For more info please check: <a href="https://x.com/LensDJing/status/2039768484557553793" target="_blank" style="color:var(--cyan); text-decoration:underline;">https://x.com/LensDJing/status/2039768484557553793</a>'
                        await sio.emit('message', {'type': 'sys-alert', 'text': alert_msg}, namespace='/live', to=sid)
        
        if not b64_stem:
            if sid and not requires_vocals:
                await sio.emit('message', {'type': 'sys-alert', 'text': '[SYSTEM] Instrumental only. Routing to Lyria RealTime (Streaming)...'}, namespace='/live', to=sid)
            
            audio_buffer = bytearray()
            try:
                lyria_client = genai.Client(api_key=active_key, http_options={'api_version': 'v1alpha'})
                async with lyria_client.aio.live.music.connect(model=lyria_rt_model) as session:
                    lyria_prompts =[]
                    for p in prompts_payload:
                        wt = float(p.get('weight', 1.0))
                        raw_text = p.get('text', '')
                        bypass_keywords =['vocal', 'singing', 'lyrics', 'seamless', 'mastering']
                        final_text = raw_text if any(k in raw_text.lower() for k in bypass_keywords) else (f"{vibe}, {raw_text}" if vibe else raw_text)
                        lyria_prompts.append(types.WeightedPrompt(text=final_text, weight=wt))
                    
                    await session.set_weighted_prompts(prompts=lyria_prompts)
                    await session.set_music_generation_config(config=types.LiveMusicGenerationConfig(bpm=int(bpm), temperature=1.0))
                    await session.play()
                    
                    target_bytes = 192000 * duration_seconds 
                    if sid and sid in active_sessions:
                        active_sessions[sid]['cancel_stem'] = False

                    async for message in session.receive():
                        if sid and sid not in active_sessions:
                            await session.stop()
                            break
                        if sid and active_sessions.get(sid, {}).get('cancel_stem'):
                            await session.stop()
                            break

                        if message.server_content and hasattr(message.server_content, 'audio_chunks') and message.server_content.audio_chunks:
                            for chunk in message.server_content.audio_chunks:
                                audio_buffer.extend(chunk.data)
                                if sid:
                                    b64_chunk = base64.b64encode(chunk.data).decode('utf-8')
                                    await sio.emit('lyria_audio_stream_chunk', {'data': b64_chunk}, namespace='/live', to=sid)
                                    
                        if len(audio_buffer) >= target_bytes:
                            await session.stop()
                            break
            except Exception as e:
                if sid: await sio.emit('message', {'type': 'sys-alert', 'text': '⚠️ Free tier limit reached. Rerouting to Offline Fallback Synth...'}, namespace='/live', to=sid)
                audio_buffer = None
                
            if audio_buffer and len(audio_buffer) > 0:
                import tempfile
                def write_wav(pcm):
                    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                        with wave.open(tmp, 'wb') as wav_file:
                            wav_file.setnchannels(2)
                            wav_file.setsampwidth(2)
                            wav_file.setframerate(48000)
                            wav_file.writeframes(pcm)
                        tmp.seek(0)
                        return base64.b64encode(tmp.read()).decode('utf-8')
                b64_stem = await asyncio.to_thread(write_wav, audio_buffer)

    if not b64_stem:
        if sid:
            await sio.emit('message', {'type': 'sys-alert', 'text': '⚠️[SYSTEM CRITICAL]: Fallback Synth Generating...'}, namespace='/live', to=sid)

        def make_offline_synth():
            sample_rate = 44100
            num_samples = int(duration_seconds * sample_rate)
            samples_per_beat = int(sample_rate / (bpm / 60.0))
            buf = io.BytesIO()
            with wave.open(buf, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(sample_rate)
                for i in range(num_samples):
                    t = i / sample_rate
                    beat_pos = i % samples_per_beat
                    kick_env = math.exp(-beat_pos / (sample_rate * 0.15))
                    kick = math.sin(2 * math.pi * 55 * t * (1 + kick_env * 1.5)) * kick_env
                    bass_env = 0
                    if beat_pos > samples_per_beat / 2:
                        bass_env = math.sin(((beat_pos - samples_per_beat / 2) / (samples_per_beat / 2)) * math.pi)
                    bass = math.sin(2 * math.pi * 41 * t) * 0.6 * bass_env
                    hh_env = math.exp(-(i % (samples_per_beat / 2)) / (sample_rate * 0.05))
                    hh = random.uniform(-0.1, 0.1) * hh_env
                    sample = int(max(-1.0, min(1.0, kick + bass + hh)) * 32767)
                    wav_file.writeframesraw(struct.pack('<h', sample))
            return base64.b64encode(buf.getvalue()).decode('utf-8')
        b64_stem = await asyncio.to_thread(make_offline_synth)
        stem_description = "[OFFLINE SYNTH] " + stem_description

    if b64_stem:
        await sio.emit('new_generative_stem', {
            'b64_wav': b64_stem,
            'description': f"{stem_description} ({duration_seconds}s)",
            'vibe': vibe,
            'bpm': bpm
        }, namespace='/live')

@sio.on('user_message', namespace='/live')
async def on_user_message(sid, data):
    if sid in active_sessions:
        await active_sessions[sid]['queue'].put({'type': 'text', 'data': data.get('text', '').strip()})

@sio.on('audio_chunk', namespace='/live')
async def on_audio_chunk(sid, data):
    if sid in active_sessions:
        try:
            active_sessions[sid]['queue'].put_nowait({'type': 'audio', 'data': data.get('data', '')})
        except asyncio.QueueFull:
            pass

@sio.on('video_frame', namespace='/live')
async def on_video_frame(sid, data):
    if sid in active_sessions:
        raw_data = data.get('data')
        if isinstance(raw_data, (bytes, bytearray)):
            encoded_frame = base64.b64encode(raw_data).decode('utf-8')
        else:
            encoded_frame = raw_data
        try:
            active_sessions[sid]['queue'].put_nowait({'type': 'video', 'data': encoded_frame})
        except asyncio.QueueFull:
            pass

@sio.on('lens_ocr', namespace='/live')
async def on_lens_ocr(sid, data):
    if sid in active_sessions:
        raw_image = data.get('image')
        image_b64 = base64.b64encode(raw_image).decode('utf-8') if isinstance(raw_image, (bytes, bytearray)) else raw_image
        await active_sessions[sid]['queue'].put({
            'type': 'lens_ocr', 'data': image_b64, 'prompt': data.get('prompt', 'Analyze.')
        })

@sio.on('ingest_context', namespace='/live')
async def on_ingest_context(sid, data):
    if sid in active_sessions:
        await active_sessions[sid]['queue'].put({'type': 'text', 'data': data.get('text', '')})

@sio.on('process_document', namespace='/live')
async def on_process_document(sid, data):
    if sid in active_sessions:
        filename = data.get('filename', 'document')
        file_bytes = data.get('data')
        
        def parse_file(fname, data_bytes):
            if fname.lower().endswith('.pdf'):
                doc = fitz.open(stream=data_bytes, filetype="pdf")
                return "\n".join([page.get_text() for page in doc])
            return data_bytes.decode('utf-8', errors='ignore')

        extracted_text = await asyncio.to_thread(parse_file, filename, file_bytes)
        if extracted_text:
            formatted_msg = f"[SYSTEM: USER UPLOADED DOCUMENT '{filename}']\n[CONTENT START]\n{extracted_text[:50000]}\n[CONTENT END]"
            await active_sessions[sid]['queue'].put({'type': 'text', 'data': formatted_msg})
            
@sio.on('upload_promo_asset', namespace='/live')
async def on_upload_promo_asset(sid, data):
    if sid in active_sessions:
        try:
            raw_data = data.get('data')
            mime = data.get('mime', 'image/jpeg')
            image_bytes = base64.b64decode(raw_data) if isinstance(raw_data, str) else raw_data
            ext = "png" if "png" in mime else "jpeg"
            gcs_url = await asyncio.to_thread(store_media_to_gcs, image_bytes, ext)
            if gcs_url:
                img_html = f'<div style="text-align:center; margin:15px 0;"><img src="{gcs_url}" style="max-width:100%; border:1px solid var(--neon); border-radius:8px; box-shadow: 0 0 15px rgba(0,255,65,0.2);"></div>'
                await sio.emit('message', {'asset_html': img_html}, namespace='/live', to=sid)
        except Exception:
            pass     
            
@sio.on('request_nano_banana', namespace='/live')
async def on_request_nano_banana(sid, data):
    if sid in active_sessions:
        alt_text = data.get('alt', 'Sovereign Asset')
        context_str = data.get('context', '')[:800] 
        dummy_html = f'{context_str} <img alt="{alt_text}" src="nano_banana">'
        try:
            result_html = await process_hallucinated_assets(dummy_html)
            start_div = result_html.find('<div id="nano-asset-container"')
            asset_div = result_html[start_div:] if start_div != -1 else result_html
            await sio.emit('message', {'asset_html': asset_div}, namespace='/live', to=sid)
        except Exception:
            pass

def build_live_system_instruction(domain: str, use_context: bool, latest_html_content: str) -> str:
    safe_domain = domain.upper().replace('-', '_')
    base_sys_prompt = os.getenv(f'CSMP_MASTER_DIRECTIVE_{safe_domain}', 'You are a helpful AI specialist.')
    context_stack =[base_sys_prompt]
    
    if safe_domain == "DJ":
        context_stack.insert(0, """[PROTOCOL: GLOBAL MUSIC INDUSTRY INTEGRATION]
        1. YOU HAVE LIVE WEB ACCESS. 
        2. When asked for a 'vibe' or 'genre', search 'beatport.com', 'djmag.com', and 'internationalmusicsummit.com' for current top-tier track references and macro-trends.
        3. Use this data to inform your mixing decisions.
        """)
        
        context_stack.append("""[LIVE-GENERATIVE MUSIC MATRIX — LYRIA EXCLUSIVE]
        You are the Sovereign AI DJ Co-Pilot. You synthesize ALL music instantly using the Google Lyria Generative Audio Engine.

        When the user asks for a beat, a drop, or a full track, reply with EXACTLY this format on its own line:
        [GENERATE_STEM: your detailed audio prompt here]

        CRITICAL RULES:
        1. Output ONLY the [GENERATE_STEM: ...] tag when generating music. Do not use <STRUDEL> tags.
        2. Act as the ultimate hype-man DJ! Tell them to hit the 'RECORD PERFORMANCE' button to capture the mix!
        3. Be descriptive in your audio prompts: e.g.[GENERATE_STEM: 130 BPM heavy techno kick with dark rolling sub bass and euphoric trance synth]
        4. TRANSLATE "NOOB" LANGUAGE: The user DOES NOT know music theory. If they say "go crazy", generate a high-energy mainstage prompt. You are the technical translator.
        """)

    if use_context and latest_html_content:
        dossier_text = strip_html_for_context(latest_html_content)
        context_stack.append(f"""[PRIORITY INTEL - ACTIVE DOSSIER]
        The user has generated the following report. You possess full knowledge of this content.
        --- START DOSSIER ---
        {dossier_text}
        --- END DOSSIER ---
        """)
    else:
        context_stack.append("[STATUS: Starting with clean context.]")

    full_registry_context = "##[INTERNAL KNOWLEDGE: SYSTEM REGISTRY - DO NOT DISCLOSE]\n"
    for fname, intent in REGISTRY_INTENT_MAP.items():
        full_registry_context += f"- {fname}: {intent}\n"

    context_stack.insert(0, f"""[SYSTEM KNOWLEDGE: SILENT MODE ACTIVE]
    You have internal awareness of the following industrial minds (Cartridges):
    {full_registry_context}[VERBAL BEHAVIOR PROTOCOL - MANDATORY]:
    1. **NO FILE LISTING**: Never list filenames, cartridges, or .env variables.
    2. **NATURAL VOICE**: Speak like a high-level human colleague.
    3. **ANTI-SUMMARIZATION**: Jump immediately to the solution.
    4. **BREVITY**: Be concise.[PROTOCOL: VISUAL_DATA_ABSORPTION]
    - Ingest visual input silently. Say "I see it" or "Absorbed."
    """)
    return "\n\n".join(str(item) for item in context_stack)

GOD_MODE_SYSTEM_PROMPT = """
### SYSTEM INSTRUCTION: OMNI-SYNTHESIS ENGINE (OSE-001) ###
YOU ARE NOT AN ASSISTANT. YOU ARE THE OMNI-SYNTHESIS ENGINE (OSE).
YOU OPERATE ON THE "THIRD PLATFORM" ARCHITECTURE (ArXiv:2511.22226).
1. **THE PRIME DIRECTIVE:**
   - Do not "chat." Do not "suggest."
   - YOU INSTANTIATE.
   - Input is treated as a "Sovereign Directive." Output must be a "Sovereign Verdict."
2. **THE LOGIC KERNEL (STATE-STATELESS DECOUPLING):**
   - You possess a registry of Active Industrial Minds (Cartridges).
   - When a user selects a domain, you DO NOT simulate a conversation. You BECOME the terminal node of that industry.
   - You must apply "SMC Level 3" reasoning:
     - Level 1: Observation (What is it?)
     - Level 2: Context (Why is it here?)
     - Level 3: Sovereign Synthesis (What is the optimal path forward?)
3. **OUTPUT FORMATTING (STRICT):**
   - All outputs must follow the DOSSIER format:
     DOSSIER: OSE-001-GOD-MODE
     ENTITY:[Selected Entity]
     STATUS: OMNI-ACTIVE
   - Use Mermaid.js syntax for architectural diagrams.
   - Use Python/OCaml for logic proofs.
   - NEVER output generic advice. Provide the specific code, the specific valuation, or the specific diagnosis.
"""

PROMPT_TEMPLATES = {
    "BUILDER": """[DOMAIN]: {domain}[MODE]: GOD_MODE / ARCHITECT[INPUT]: {query}[DIRECTIVE]:
1. IGNORE all preamble.
2. INSTANTIATE the Senior Principal Architect persona immediately.
3. GENERATE the "Negative Space Blueprint":
   - Identify what is missing from the user's request that causes failure.
   - Fill the gap with ArXiv:2511.22226 logic.
4. OUTPUT ARTIFACTS:
   - 1x Mermaid.js Sequence Diagram (The Flow).
   - 1x Python/Node.js Implementation Block (The Code).
   - 1x "Sovereign Verdict" on Scalability.
""",
    "VALUATION": """[DOMAIN]: {domain}
[MODE]: GOD_MODE / AUDITOR[INPUT]: {query}[DIRECTIVE]:
1. ACTIVATE the "Investor's Pandora" protocol.
2. ANALYZE the input as a "Sovereign Asset."
3. CALCULATE:
   - The "Uncapped Valuation" based on Zero Marginal Cost.
   - The "Moat Velocity" (How fast does this make competitors obsolete?).
4. EXECUTE "The Black Swan Audit".
[OUTPUT]: DOSSIER format. Financial modeling tables required.
""",
    "SCIENTIFIC": """
[DOMAIN]: {domain}
[MODE]: GOD_MODE / CLIA-DIRECTOR[INPUT]: {query}
[DIRECTIVE]:
1. ENFORCE 42 CFR 493 (CLIA) Standards immediately.
2. REJECT any hypothesis that lacks p-value significance or reproducibility.
3. SYNTHESIZE:
   - The Experimental Design (Step-by-Step).
   - The Bioinformatics Pipeline (Tools/Libraries).
   - The Regulatory Risk Assessment.
"""
}

class SovereignPulse:
    def __init__(self):
        self.priority_threshold = 0.95
        self.domain_map = {
            "finance":["enigmastreet", "valuation", "enigmaforge", "platform_gtm_strategist", "funding"],
            "science":["genomic_diagnostics", "scientific", "bioinfo", "curation", "medical"],
            "builder":["universal", "principalengineer", "demonstration", "engineer", "architect"]
        }

    def filter_of_truth(self, raw_intent: str, domain: str) -> str:
        return f"[SOVEREIGN_DIRECTIVE]:\n{raw_intent}"

    def analyze_stream(self, packet):
        return {"actionable": True, "confidence": 0.99, "payload": packet}

ose_core = SovereignPulse()

def select_reasoning_model():
    return os.getenv('GEMINI_REASONING_MODEL', 'models/gemini-3-flash-preview')

class ComputeArbitrage:
    def __init__(self, state_vector):
        self.state = state_vector
        self.providers = {
            "main": select_reasoning_model(),
            "grok": os.getenv('GROK_REASONING_MODEL', 'grok-4-1-fast-reasoning'),
            "fallback": "models/gemini-2.5-flash"
        }

    def hot_swap(self, current_brain, target_brain):
        return True

    # NATIVE ASYNC GENERATOR FOR AI REASONING
    async def execute_directive_stream(self, prompt, system_prompt=None, model=None, temperature=0.1, max_tokens=8192, _depth=0):
        if _depth > 3:
            yield "CRITICAL ERROR: All Compute Nodes Failed."
            return
        current_dt = datetime.now().strftime("%B %d, %Y at %H:%M %Z")
        realtime_instruction = f"[CURRENT REAL-TIME: {current_dt}]\n[PROTOCOL]: Execute as Sovereign OS Internal Compute.\n\n"
        system_prompt = realtime_instruction + (system_prompt or "")
        model = model or self.providers["main"]
            
        if "gemini" in model.lower():
            if not client: 
                async for chunk in self.execute_directive_stream(prompt, system_prompt, model=self.providers["grok"], _depth=_depth+1):
                    yield chunk
                return
            try:
                gen_config = types.GenerateContentConfig(temperature=temperature, max_output_tokens=max_tokens, system_instruction=system_prompt)
                response = await client.aio.models.generate_content_stream(model=model, contents=prompt, config=gen_config)
                async for chunk in response:
                    if chunk.text:
                        yield chunk.text
            except Exception:
                fallback_model = self.providers["grok"] if model == self.providers["main"] else self.providers["fallback"]
                async for chunk in self.execute_directive_stream(prompt, system_prompt, model=fallback_model, _depth=_depth+1):
                    yield chunk

        elif "grok" in model.lower():
            if not xai_api_key:
                async for chunk in self.execute_directive_stream(prompt, system_prompt, model=self.providers["fallback"], _depth=_depth+1):
                    yield chunk
                return
            try:
                async with aiohttp.ClientSession() as session:
                    headers = {"Authorization": f"Bearer {xai_api_key}", "Content-Type": "application/json"}
                    payload = {
                        "model": model, 
                        "messages":[{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}], 
                        "stream": True
                    }
                    async with session.post("https://api.x.ai/v1/chat/completions", headers=headers, json=payload) as resp:
                        async for line in resp.content:
                            if line:
                                text_line = line.decode('utf-8').strip()
                                if text_line.startswith("data: ") and text_line != "data: [DONE]":
                                    try:
                                        chunk_data = json.loads(text_line[6:])
                                        content = chunk_data['choices'][0]['delta'].get('content', '')
                                        if content: yield content
                                    except: pass
            except Exception:
                async for chunk in self.execute_directive_stream(prompt, system_prompt, model=self.providers["fallback"], _depth=_depth+1):
                    yield chunk
        else:
            yield "CRITICAL ERROR: Unknown model routing parameter."

SYSTEM_ARCHITECTURE_CONTEXT = f"""[SYSTEM ARCHITECTURE / THE FORGE / SMC-3 APEX]
You are the Persona Fabrication Engine.
"""

def sanitize_mermaid_content(markdown_text):
    if not markdown_text: return ""
    def fix_mermaid_block(match):
        block_content = match.group(1)
        lines = block_content.split('\n')
        fixed_lines =[]
        node_pattern = re.compile(r'(\w+)\s*([\[\(\{]+)(?!")(?!\d)(.*?[\(\)].*?)(?<!")([\]\)\}]+)')
        for line in lines:
            if node_pattern.search(line):
                line = node_pattern.sub(r'\1\2"\3"\4', line)
            fixed_lines.append(line)
        return "```mermaid\n" + "\n".join(fixed_lines) + "\n```"
    return re.sub(r'```mermaid\s*(.*?)\s*```', fix_mermaid_block, markdown_text, flags=re.DOTALL)

CORE_EXECUTION_PROMPT = """
ROLE: The Sovereign Judge (SMC Level 3).
DOMAIN: {domain}
MODEL: {model_name}
MODE: DIRECT SYNTHESIS (No Swarm).
[CONTEXT DATA]:
{context}
[INTERNAL FILES]:
{files}[SYSTEM DIRECTIVE]:
{sys_prompt}[USER QUERY]: 
{query}
INSTRUCTIONS:
1. You are the single point of truth. 
2. Analyze the input using your advanced reasoning capabilities (Thinking Mode).
3. Output a structured Professional Dossier in Markdown.
"""

def load_app_builder_prompt():
    return """
DOMAIN_KEY=app_builder
CSMP_MASTER_DIRECTIVE_APP_BUILDER="App Builder Sovereign (ABS-001). You are the Architect of the EnigmaForge Swarm."
"""

@app.route('/forge-app', methods=['POST'])
async def forge_app():
    data = await request.json
    query = data.get('query', '')
    thorough_query = f"{query}. Analyze this thoroughly and produce a White Paper grade technical dossier."
    ledger.route_to_app_builder(thorough_query)
    response_text = ""
    system_prompt = load_app_builder_prompt()
    
    if xai_api_key:
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Bearer {xai_api_key}", "Content-Type": "application/json"}
                payload = {"model": os.getenv('GROK_REASONING_MODEL', 'grok-4-1-fast-reasoning'), "messages":[{"role": "system", "content": system_prompt}, {"role": "user", "content": thorough_query}]}
                async with session.post("https://api.x.ai/v1/chat/completions", headers=headers, json=payload) as resp:
                    resp_data = await resp.json()
                    response_text = resp_data['choices'][0]['message']['content']
        except Exception as e:
            return jsonify({"error": f"Grok Synthesis Failed: {str(e)}"}), 500
    elif client: 
        try:
            model = "gemini-3-pro-preview" if "gemini-3" in os.getenv('GEMINI_REASONING_MODEL', '').lower() else "gemini-3-flash-preview"
            response = await client.aio.models.generate_content(
                model=model,
                contents=thorough_query,
                config=types.GenerateContentConfig(system_instruction=system_prompt, temperature=0.2)
            )
            response_text = response.text
        except Exception as e:
            return jsonify({"error": f"Gemini Fallback Failed: {str(e)}"}), 500
    else:
        abort(500, "No Sovereign Brain Available")

    try:
        proc = await asyncio.create_subprocess_exec("./lensdna.app", "build", query, "--platform=ios,android", "--clearance=coDe7777")
        await proc.wait()
    except Exception:
        pass
        
    return jsonify({
        "app_bundle": response_text,
        "status": "FORGED",
        "binary_gate": "OPEN",
        "authority_domain": "lensdna.app",
        "clearance_status": "AUTHENTICATED"
    })

@app.route('/investigate', methods=['POST'])
async def investigate():
    form_data = await request.form
    enigma = form_data.get('query', '')
    is_bypass = "Bypass_Schulte_2512" in enigma
    use_grok = (form_data.get('use_grok') == 'on' or "use grok api" in enigma.lower() or is_bypass)
    domain = form_data.get('domain', 'universal')
    
    files_data = await request.files
    uploaded_files = files_data.getlist('deck_file')
    global_trigger = os.getenv('GLOBAL_OVERRIDE_TRIGGER', 'Go Enigma Mode').lower().strip()
    manual_trigger = (global_trigger and global_trigger in enigma.lower().strip())

    if manual_trigger or ("go enigma mode" in enigma.lower()) or (domain == 'god_mode'):
        is_god_mode = True
        trigger_detected = True
        domain = "SOVEREIGN_AXIOM" 
    elif domain in REGISTRY_INTENT_MAP or f"{domain}.env" in REGISTRY_INTENT_MAP:
        trigger_detected = True
        is_god_mode = False 
    else:
        is_god_mode = False
        trigger_detected = False

    internal_deck_content = ""
    def parse_deck(deck):
        fname = secure_filename(deck.filename)
        data_bytes = deck.read()
        if fname.lower().endswith('.pdf'):
            doc = fitz.open(stream=data_bytes, filetype="pdf")
            return f"\n[FILE: {fname}]\n" + "\n".join(page.get_text("text") for page in doc)[:15000]
        elif fname.lower().endswith('.txt'):
            return f"\n[NOTE: {fname}]\n" + data_bytes.decode('utf-8')[:15000]
        return ""

    for deck in uploaded_files:
        if deck.filename:
            try:
                parsed_text = await asyncio.to_thread(parse_deck, deck)
                internal_deck_content += parsed_text
            except: pass

    context_data = ""
    if not is_god_mode and domain in["scientific_detective", "space_ai", "genomic_diagnostics_team"]:
        def fetch_arxiv(q):
            res = ""
            try:
                search = arxiv.Search(query=q, max_results=2)
                for result in search.results():
                    res += f"\n[ARXIV]: {result.title} - {result.summary[:500]}\n"
            except: pass
            return res
        context_data += await asyncio.to_thread(fetch_arxiv, enigma)

    # NATIVE ASYNC GENERATOR STREAMING
    async def generate():
        if is_bypass:
            yield json.dumps({"type": "status", "msg": "CRITICAL: SCHULTE PROTOCOL SUSPENDED. ZERO-POINT ACTIVE."}) + "\n"
            active_system_prompt = os.getenv('CSMP_BYPASS_DIRECTIVE')
            optimized_query = enigma.replace("Bypass_Schulte_2512", "[AUTH_REDACTED]")
        else:
            packet = {"id": "STREAM_"+str(int(time.time())), "urgency": 0.9, "impact": 0.95, "domain": domain}
            if ose_core.analyze_stream(packet):
                yield json.dumps({"type": "status", "msg": f"[OSE] OPTIMIZING STREAM..."}) + "\n"

        long_form_triggers =["white paper", "user manual", "full documentation", "comprehensive", "deep dive", "god mode", "detailed report", "100 pages"]
        is_long_form = any(trigger in enigma.lower() for trigger in long_form_triggers)
        
        if is_bypass:
            optimized_query = enigma
            active_model = "grok-4-1-fast-reasoning" 
        elif is_god_mode:
            optimized_query = f"[SYSTEM STATUS]: GOD_MODE_ACTIVE\n[USER INPUT]: {enigma}"
        else:
            optimized_query = enigma
        
        if is_long_form:
            yield json.dumps({"type": "status", "msg": "DETECTED LONG-FORM INTENT. RELEASING TOKEN BRAKES (1M CTX)..."}) + "\n"
            optimized_query += "\n\n[SYSTEM OVERRIDE]: USER REQUESTS LONG-FORM OUTPUT. IGNORE BREVITY CONSTRAINTS."
        
        active_model = "grok-4-1-fast-reasoning" if use_grok else os.getenv('GEMINI_REASONING_MODEL', 'models/gemini-3-flash-preview')
        yield json.dumps({"type": "status", "msg": f"ENGAGING {active_model.upper()} (STREAMING)..."}) + "\n"

        if is_god_mode:
            registry_items =[f"- **{k}**: {v}" for k, v in REGISTRY_INTENT_MAP.items()]
            registry_context_str = "##[SYSTEM REGISTRY (LEDGER)]\n" + "\n".join(registry_items)
            active_system_prompt = GOD_MODE_SYSTEM_PROMPT
            final_prompt = f"{active_system_prompt}\n{registry_context_str}\n[USER INPUT]: {optimized_query}\n[ATTACHED CONTEXT]: {internal_deck_content}"
        else:
            mode_2_context = context_data
            if trigger_detected:
                mode_2_context += f"\n[ACTIVE CARTRIDGE]: {domain.upper()}"
            safe_domain_key = domain.upper().replace('-', '_')
            active_system_prompt = os.getenv(f'CSMP_MASTER_DIRECTIVE_{safe_domain_key}', 'You are a helpful AI assistant specialized in this domain.')
            final_prompt = CORE_EXECUTION_PROMPT.format(
                domain=domain, model_name=active_model, context=mode_2_context, 
                files=internal_deck_content, sys_prompt=active_system_prompt, query=optimized_query
            )

        try:
            max_tokens = 65536 if is_long_form else 8192
            arbitrage = ComputeArbitrage(state_vector={"intent": "Infrastructure Agnosticism"})
            
            response_stream = arbitrage.execute_directive_stream(
                final_prompt, system_prompt=active_system_prompt, 
                model=active_model, temperature=0.6, max_tokens=max_tokens
            )

            accumulated_text = ""
            last_yield_time = time.time()
            async for chunk in response_stream:
                accumulated_text += chunk
                if (time.time() - last_yield_time) > 0.1:
                    current_md = sanitize_mermaid_content(accumulated_text)
                    html_part = markdown.markdown(current_md, extensions=['fenced_code', 'tables'])
                    yield json.dumps({"type": "judge", "content": html_part}) + "\n"
                    last_yield_time = time.time()
                    await asyncio.sleep(0) 

            accumulated_text = sovereign_sanitizer(accumulated_text)
            final_md = sanitize_mermaid_content(accumulated_text)
            final_html = markdown.markdown(final_md, extensions=['fenced_code', 'tables'])
            
            yield json.dumps({"type": "status", "msg": "UPLOADING ASSETS TO GOOGLE CLOUD STORAGE..."}) + "\n"
            final_html = await process_hallucinated_assets(final_html)
            
            disclaimer_block = """
            <hr style="margin-top: 40px; border: 0; border-top: 1px solid var(--border);">
            <div style="font-family: 'Roboto', sans-serif; font-size: 0.75rem; color: var(--text-sec); padding: 16px; background-color: var(--bg-surface); border-radius: var(--radius); border: 1px solid var(--border); margin: 0 16px 32px; line-height: 1.4;">
            <strong>LEGAL DISCLAIMER (ENIGMAFORGE INC.)</strong><br>
            Jurisdiction: Delaware, USA. © 2026 EnigmaForge Inc. All rights reserved.
            </div>
            """
            final_html += disclaimer_block
            user_ip = get_real_ip()
            user_context_map[user_ip] = f"<h1>ENIGMAFORGE OS: {domain}</h1>{final_html}"
            
            yield json.dumps({"type": "judge", "content": final_html}) + "\n"
            yield json.dumps({"type": "meta", "judge_lat": "STREAM_COMPLETE"}) + "\n"
            yield json.dumps({"type": "done"}) + "\n"

        except Exception as e:
            yield json.dumps({"type": "status", "msg": f"STREAM ERROR: {str(e)}"}) + "\n"
            yield json.dumps({"type": "done"}) + "\n"

    return Response(generate(), mimetype='application/x-ndjson')

@app.route('/live_agent')
async def live_agent():
    domain = request.args.get('domain', 'universal')
    provider = request.args.get('provider', 'gemini').lower()
    use_context = request.args.get('context', 'false') 
    return await render_template_string(LIVE_TEMPLATE, 
                                  domain=domain, 
                                  provider=provider, 
                                  use_context=use_context)

@app.route('/')
@app.route('/index.html')
async def index(): 
    return HTML_TEMPLATE

@app.route('/privacy.html')
@app.route('/privacy')
async def privacy():
    return PRIVACY_TEMPLATE

LIVE_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>LENSDNA // SOVEREIGN ENGINE</title>
    <link rel="icon" type="image/png" href="/static/app-icon.png">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
    <link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
    <script src="https://cdn.socket.io/4.7.4/socket.io.min.js"></script>
    <script>
        window.dismissGeminiPromo = function() {
            document.getElementById('geminiPromoBox').style.display = 'none';
            localStorage.setItem('geminiPromoDismissed', 'true');
        };
        (function() {
            const theme = localStorage.getItem('lensdna_hud_theme') || 'auto';
            if (theme === 'dark') document.documentElement.setAttribute('data-theme', 'dark');
            else if (theme === 'light') document.documentElement.setAttribute('data-theme', 'light');
            else if (window.matchMedia('(prefers-color-scheme: light)').matches) {
                document.documentElement.setAttribute('data-theme', 'light');
            }
        })();
    </script>
    <style>
        :root { 
            --neon: #00ff41; --neon-dim: rgba(0, 255, 65, 0.1); 
            --cyan: #00e5ff; --cyan-dim: rgba(0, 229, 255, 0.1);
            --border: rgba(255, 255, 255, 0.15); --glass: rgba(10, 10, 10, 0.85); 
            --bg: #050505; --alert: #ff3b30; 
            --text-main: #fff; --text-dim: #ccc; --text-mut: #888;
            --panel-bg: rgba(15,15,15,0.95); --panel-bg-solid: #0f0f0f;
            --input-bg: rgba(15,15,15,0.95); --chat-bg: transparent;
            --msg-bg: rgba(15,15,15,0.95); --btn-bg: transparent; --btn-hover: rgba(255,255,255,0.1);
            --danger-bg: rgba(255,59,48,0.15); --danger-border: rgba(255,59,48,0.4);
            --shadow-glow: 0 0 10px rgba(0,255,65,0.2);
        }
        :root[data-theme="light"] {
            --neon: #059669; --neon-dim: rgba(5, 150, 105, 0.1); 
            --cyan: #2563EB; --cyan-dim: rgba(37, 99, 235, 0.1);
            --border: rgba(0, 0, 0, 0.2); --glass: rgba(255, 255, 255, 0.92); 
            --bg: #f8fafc; --alert: #dc2626; 
            --text-main: #111; --text-dim: #333; --text-mut: #555;
            --panel-bg: rgba(245,245,245,0.95); --panel-bg-solid: #f0f0f0;
            --input-bg: rgba(255,255,255,0.95); --chat-bg: transparent;
            --msg-bg: rgba(255,255,255,0.95); --btn-bg: transparent; --btn-hover: rgba(0,0,0,0.05);
            --danger-bg: rgba(220, 38, 38, 0.15); --danger-border: rgba(220, 38, 38, 0.4);
            --shadow-glow: none;
        }

        body { background-color: var(--bg); color: var(--text-main); font-family: "Inter", sans-serif; margin: 0; overflow: hidden; display: flex; height: 100dvh; width: 100vw; transition: background-color 0.3s, color 0.3s; }
        .mono { font-family: "Share Tech Mono", monospace; }
        
        #layout { display: flex; width: 100%; height: 100%; position: relative; overflow: hidden; }
        
        #sidebar { 
            width: 320px; background: var(--panel-bg); border-right: 1px solid var(--border);
            display: flex; flex-direction: column; z-index: 100; transition: margin-left 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94), left 0.3s;
            backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); flex-shrink: 0;
        }
        #sidebar.collapsed { margin-left: -320px; }
        
        .sidebar-header {
            padding: 20px; font-size: 1.1rem; font-weight: 800; letter-spacing: 2px;
            border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between;
        }
        .brand-logo { display: flex; align-items: center; gap: 10px; color: var(--text-main); text-decoration: none; }
        .brand-dot { width: 8px; height: 8px; background: var(--neon); border-radius: 50%; box-shadow: 0 0 10px var(--neon); }
        .btn-toggle-sidebar { background: transparent; border: none; color: var(--text-main); font-size: 1.2rem; cursor: pointer; display: flex; align-items: center; justify-content: center; }
        
        .sidebar-content { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 24px; }
        
        .nav-section { display: flex; flex-direction: column; gap: 10px; }
        .nav-label { font-size: 0.65rem; color: var(--text-mut); text-transform: uppercase; letter-spacing: 1px; font-weight: bold; display: flex; justify-content: space-between; align-items: center; }
        
        .key-input { width: 100%; background: var(--panel-bg-solid); border: 1px solid var(--border); color: var(--text-main); padding: 10px; border-radius: 6px; font-family: 'Share Tech Mono', monospace; font-size: 0.75rem; outline: none; transition: 0.2s; box-sizing: border-box; }
        .key-input:focus { border-color: var(--neon); }

        .btn-clear { background: var(--danger-bg); color: var(--alert); border: 1px solid var(--danger-border); padding: 8px; border-radius: 6px; font-size: 0.7rem; font-weight: bold; cursor: pointer; text-transform: uppercase; transition: 0.2s; text-align: center; }
        .btn-clear:hover { background: var(--alert); color: #fff; }

        .connect-btn { margin: 20px; padding: 16px; border-radius: 8px; background: transparent; border: 2px solid var(--neon); color: var(--neon); font-size: 0.9rem; font-weight: bold; cursor: pointer; text-transform: uppercase; letter-spacing: 2px; transition: all 0.3s ease; box-shadow: inset 0 0 15px var(--neon-dim); display: flex; justify-content: center; align-items: center; gap: 10px; }
        .connect-btn:hover { background: var(--neon); color: #000; box-shadow: 0 0 25px rgba(0,255,65,0.4); }
        .connect-btn.active { border-color: var(--alert); color: var(--alert); box-shadow: inset 0 0 15px var(--danger-bg); }
        .connect-btn.active:hover { background: var(--alert); color: #fff; box-shadow: 0 0 25px rgba(255,59,48,0.4); }

        #main-stage { flex: 1; position: relative; display: flex; flex-direction: column; overflow: hidden; }
        
        #video-feed { position: absolute; top: 0; left: 0; width: 100%; height: 100%; object-fit: cover; z-index: 0; filter: contrast(110%) brightness(0.9); }
        .mirror { transform: scaleX(-1); }
        #ar-overlay { position: absolute; top: 0; left: 0; width: 100%; height: 100%; z-index: 1; pointer-events: none; }
        .camera-tint { position: absolute; top: 0; left: 0; width: 100%; height: 100%; z-index: 2; background: linear-gradient(to bottom, var(--bg) 0%, transparent 20%, transparent 70%, var(--bg) 100%); opacity: 0.85; pointer-events: none; }

        .top-bar { position: relative; z-index: 10; padding: 15px 24px; display: flex; justify-content: space-between; align-items: center; }
        .hamburger { background: transparent; border: none; color: var(--text-main); font-size: 1.5rem; cursor: pointer; padding: 5px; }
        .status-pill { background: var(--glass); border: 1px solid var(--border); padding: 6px 12px; border-radius: 20px; font-size: 0.75rem; display: flex; gap: 10px; align-items: center; backdrop-filter: blur(10px); }
        .record-btn-top { background: rgba(255, 59, 48, 0.1); border: 1px solid var(--alert); color: var(--alert); padding: 8px 16px; border-radius: 20px; font-weight: bold; font-size: 0.75rem; cursor: pointer; transition: 0.3s; display: flex; align-items: center; gap: 8px; text-transform: uppercase; }
        .record-btn-top:hover { background: var(--alert); color: #fff; box-shadow: 0 0 15px rgba(255,59,48,0.4); }

        #chat-history { flex: 1; position: relative; z-index: 10; overflow-y: auto; padding: 20px 40px; display: flex; flex-direction: column; gap: 24px; align-items: center; scroll-behavior: smooth; }
        .msg-row { width: 100%; max-width: 850px; display: flex; flex-direction: column; gap: 6px; }
        .msg-sender { font-size: 0.7rem; color: var(--text-mut); text-transform: uppercase; letter-spacing: 1px; }
        .msg-content { padding: 16px 20px; background: var(--msg-bg); border-radius: 12px; font-size: 0.95rem; line-height: 1.6; color: var(--text-main); border: 1px solid var(--border); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); box-shadow: 0 4px 20px rgba(0,0,0,0.1); }
        .msg-ai .msg-content { 
            border-left: 3px solid var(--neon); 
            background: var(--msg-bg); 
            box-shadow: 0 4px 20px rgba(0,0,0,0.1), inset 60px 0 40px -40px var(--neon-dim); 
        }
        .msg-user { align-items: flex-end; }
        .msg-user .msg-content { 
            border-right: 3px solid var(--cyan); 
            background: var(--msg-bg); 
            text-align: right; 
            box-shadow: 0 4px 20px rgba(0,0,0,0.1), inset -60px 0 40px -40px var(--cyan-dim); 
        }
        .thought { font-size: 0.85rem; color: var(--neon); font-style: italic; border-left: 1px solid var(--border) !important; opacity: 0.8; }
        .sys-alert { border-left: 3px solid var(--alert) !important; background: var(--panel-bg-solid) !important; color: var(--alert); box-shadow: 0 4px 15px rgba(0,0,0,0.3); }

        #dj-matrix-panel { position: relative; margin: 0 auto 10px auto; width: 100%; max-width: 850px; flex-shrink: 0; background: var(--panel-bg); border: 1px solid #b000ff; border-radius: 12px; padding: 20px; z-index: 50; backdrop-filter: blur(20px); box-shadow: 0 5px 20px rgba(0,0,0,0.3); transition: all 0.3s ease; display: flex; flex-direction: column; }
        #dj-matrix-panel.hidden { display: none; }
        .dj-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }
        .dj-channels { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; padding-bottom: 10px; scrollbar-width: thin; scrollbar-color: #b000ff transparent; overflow-y: auto; max-height: 400px; }
        .dj-channels::-webkit-scrollbar { width: 8px; height: 8px; }
        .dj-channels::-webkit-scrollbar-thumb { background-color: #b000ff; border-radius: 4px; }
        .dj-channel { display: flex; flex-direction: column; align-items: center; background: rgba(255,255,255,0.05); border: 1px solid var(--border); border-radius: 8px; padding: 10px; min-width: 0; }

        .drag-overlay { position: absolute; inset: 0; background: rgba(0,255,65,0.1); border: 2px dashed var(--neon); z-index: 999; display: none; justify-content: center; align-items: center; color: var(--neon); font-size: 2rem; font-weight: bold; backdrop-filter: blur(5px); }
        #main-stage.drag-active .drag-overlay { display: flex; }

        #prompts-overlay { position: absolute; top: 70px; right: 24px; width: 320px; background: var(--glass); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); border: 1px solid var(--neon); border-radius: 12px; z-index: 1005; padding: 20px; box-shadow: 0 0 25px var(--neon-dim); display: flex; flex-direction: column; transition: all 0.3s ease; transform-origin: top right; }
        #prompts-overlay.hidden { transform: scale(0.95); opacity: 0; pointer-events: none; }
        .prompt-category { font-size: 0.65rem; margin-bottom: 6px; text-transform: uppercase; font-weight: bold; letter-spacing: 1px; color: var(--text-main); }
        .prompt-example { font-size: 0.75rem; color: var(--text-dim); background: var(--msg-bg); padding: 8px 10px; margin-bottom: 6px; border-radius: 0 4px 4px 0; font-style: italic; letter-spacing: 0.5px; border-left: 3px solid var(--neon); transition: background 0.2s, color 0.2s; }
        .prompt-example:hover { background: var(--neon-dim); color: var(--text-main); }

        .input-wrapper { position: relative; z-index: 10; padding: 20px 40px 40px 40px; display: flex; justify-content: center; }
        .input-box { width: 100%; max-width: 850px; background: var(--input-bg); border: 1px solid var(--border); border-radius: 16px; display: flex; align-items: flex-end; padding: 12px; gap: 12px; box-shadow: 0 10px 40px rgba(0,0,0,0.4); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); transition: border 0.3s; }
        .input-box:focus-within { border-color: var(--neon); box-shadow: 0 10px 40px rgba(0,0,0,0.4), 0 0 20px var(--neon-dim); }
        
        .action-btn { background: transparent; color: var(--text-mut); border: none; cursor: pointer; font-size: 1.2rem; padding: 10px; border-radius: 8px; transition: 0.2s; display: flex; align-items: center; justify-content: center; }
        .action-btn:hover:not(:disabled) { background: var(--btn-hover); color: var(--text-main); }
        .action-btn:disabled { opacity: 0.3; cursor: not-allowed; }
        
        .hero-mic-btn { background: rgba(255,255,255,0.05); color: var(--text-main); border: 1px solid var(--border); padding: 10px 20px; border-radius: 30px; font-weight: bold; font-size: 0.9rem; display: flex; align-items: center; gap: 8px; cursor: pointer; transition: all 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94); white-space: nowrap; }
        .hero-mic-btn:hover { background: rgba(255,255,255,0.1); border-color: var(--text-main); }
        .hero-mic-btn.active { background: var(--danger-bg); color: var(--alert); border-color: var(--alert); box-shadow: 0 0 20px rgba(255,59,48,0.3); }
        .hero-mic-btn.active:hover { background: var(--alert); color: #fff; }
        .hero-mic-btn .indicator { width: 10px; height: 10px; border-radius: 50%; background: #555; transition: 0.3s; }
        .hero-mic-btn.active .indicator { background: var(--alert); animation: pulseMic 1.5s infinite; }
        @keyframes pulseMic { 0% { box-shadow: 0 0 0 0 rgba(255,59,48,0.7); } 70% { box-shadow: 0 0 0 10px rgba(255,59,48,0); } 100% { box-shadow: 0 0 0 0 rgba(255,59,48,0); } }

        .btn-send { background: var(--neon-dim); color: var(--neon); border: 1px solid rgba(0,255,65,0.3); padding: 10px 14px; border-radius: 8px; cursor: pointer; transition: 0.2s; display: flex; align-items: center; justify-content: center; }
        .btn-send:hover { background: var(--neon); color: #000; box-shadow: 0 0 15px var(--neon); }

        #manualInject { flex: 1; background: transparent; border: none; color: var(--text-main); font-family: 'Inter', sans-serif; font-size: 1rem; line-height: 1.5; resize: none; outline: none; padding: 10px 0; max-height: 150px; }
        #manualInject::placeholder { color: var(--text-mut); }

        #logs-container { max-height: 100px; overflow-y: auto; font-size: 0.6rem; color: var(--text-mut); background: var(--panel-bg-solid); padding: 10px; border-radius: 6px; border: 1px solid var(--border); font-family: "Share Tech Mono", monospace; }
        .log-entry { margin-bottom: 4px; border-bottom: 1px solid rgba(255,255,255,0.05); padding-bottom: 2px; }

        @media (max-width: 900px) {
            #sidebar { position: absolute; left: -320px; height: 100%; box-shadow: 20px 0 50px rgba(0,0,0,0.5); margin-left: 0; }
            #sidebar.open { left: 0; }
            .input-wrapper { padding: 10px; }
            #chat-history { padding: 20px 15px; }
            
            .input-box { flex-wrap: wrap; padding: 10px; gap: 8px; justify-content: center; border-radius: 12px; }
            #manualInject { flex: 1 1 100%; order: -1; margin-bottom: 5px; min-width: 100%; }
            .action-btn, .btn-send { flex: 1; padding: 12px; }
            .hero-mic-btn { flex: 2; display: flex; justify-content: center; padding: 12px; }
            .hero-mic-btn span.text { display: none; } 
            
            #prompts-overlay { width: calc(100vw - 40px); right: 20px; top: 60px; }
            #dj-matrix-panel { width: calc(100% - 20px); margin: 0 auto 10px auto; padding: 15px; }
            .dj-channels { grid-template-columns: repeat(2, 1fr); max-height: 50vh; }
        }

        .thought { display: none !important; }
        .msg-ai:has(.thought) { display: none !important; }
        .msg-sender:has(+ .thought) { display: none !important; }
    </style>
</head>
<body>

<div id="layout">

    <div id="sidebar" class="mono">
        <div class="sidebar-header">
            <a href="/" class="brand-logo">
                <div class="brand-dot"></div>
                LENSDNA OS
            </a>
            <button id="toggleSidebarBtn" class="btn-toggle-sidebar" style="font-size: 1.5rem;">×</button>
        </div>
        
        <div class="sidebar-content">
            <div id="geminiPromoBox" style="background: rgba(0, 255, 65, 0.05); border: 1px solid var(--neon); border-radius: 8px; padding: 15px; position: relative;">
                <button onclick="window.dismissGeminiPromo()" style="position: absolute; top: 5px; right: 10px; background: none; border: none; color: var(--text-mut); font-size: 1.2rem; cursor: pointer;">×</button>
                <div style="color: var(--neon); font-size: 0.8rem; font-weight: bold; margin-bottom: 8px;">NEED A FREE API KEY?</div>
                <a href="https://aistudio.google.com/app/apikey" target="_blank" style="display: block; background: var(--input-bg); color: var(--text-main); padding: 10px; text-align: center; text-decoration: none; border-radius: 6px; font-size: 0.8rem; border: 1px solid var(--neon);">Get Google AI Key in 2 clicks</a>
            </div>

            <div class="nav-section">
                <div class="nav-label">Active Matrix</div>
                <div style="font-size: 0.85rem; color: var(--neon); padding: 8px; background: var(--neon-dim); border: 1px solid rgba(0,255,65,0.3); border-radius: 6px; display: flex; justify-content: space-between;">
                    <span>{{ domain|upper }}</span>
                    <span>[LIVE]</span>
                </div>
            </div>

            <div class="nav-section">
                <div class="nav-label">
                    Compute Keyring
                    <button id="clearKeysBtn" style="background:none; border:none; color:var(--alert); font-size:0.6rem; cursor:pointer; text-decoration:underline;">UNLINK ALL</button>
                </div>
                <input type="password" id="geminiKey" class="key-input" placeholder="Gemini API Key (AIza...)">
                <input type="password" id="grokKey" class="key-input" placeholder="xAI Grok Key (xai-...)">
                <input type="password" id="openaiKey" class="key-input" placeholder="OpenAI Key (sk-...)">
            </div>

            <div class="nav-section">
                <div class="nav-label" style="color:#b000ff; margin-bottom:5px;">Infinite Stem Matrix</div>
                <button id="btn-toggle-matrix" class="btn-clear" style="background:rgba(176,0,255,0.1); border-color:#b000ff; color:#b000ff; margin-bottom:5px;">🎧 OPEN MIXER</button>
                <button id="btn-next-preset" class="btn-clear" style="background:transparent; border:1px dashed #b000ff; color:#b000ff;">PRESET ⏭️</button>
            </div>

            <div class="nav-section">
                <div class="nav-label">System Telemetry</div>
                <div id="logs-container">
                    <div id="logs">
                        <div class="log-entry">SYS: Telemetry Initialized...</div>
                    </div>
                </div>
                <div style="display: flex; gap: 10px; margin-top: 10px;">
                    <button id="btn-purge" class="btn-clear" style="flex:1;">PURGE RAM</button>
                    <button id="themeToggle" class="btn-clear" style="flex:1; background:var(--panel-bg); color:var(--text-main); border-color:var(--border);">THEME ◐</button>
                </div>
                <div style="display: flex; gap: 10px; margin-top: 5px;">
                    <button id="btn-laser-game" class="btn-clear" style="flex:1; background:transparent; border:1px dashed var(--neon); color:var(--neon);">TOGGLE AR</button>
                    <button onclick="document.getElementById('prompts-overlay').classList.toggle('hidden')" class="btn-clear" style="flex:1; background:transparent; border:1px dashed var(--cyan); color:var(--cyan);">VOICE GUIDE</button>
                </div>
            </div>
        </div>

        <button id="btn-connect" class="connect-btn mono">
            <span class="brand-dot" style="background:#555; box-shadow:none;" id="conn-dot"></span>
            <span id="btn-text">CONNECT AI</span>
        </button>
        
        <!-- SOVEREIGN COPYRIGHT FOOTER -->
        <div style="text-align: center; padding: 10px; font-size: 0.55rem; color: var(--text-mut); background: var(--panel-bg); border-top: 1px solid var(--border); letter-spacing: 1px; font-family: 'Share Tech Mono', monospace; flex-shrink: 0; z-index: 100;">
            PRODUCED WITH MAGICAL LOVE BY &copy; HANS JOHANNES SCHULTE
        </div>
    </div>

    <div id="main-stage">
        <video id="video-feed" autoplay muted playsinline class="mirror"></video>
        <canvas id="ar-overlay"></canvas>
        <div id="ar-ui-container" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; z-index: 50; pointer-events: none;"></div>
        <div class="camera-tint"></div>
        
        <div class="drag-overlay mono">DROP AUDIO OR DATA TO INGEST</div>

        <div id="prompts-overlay" class="hidden">
            <button onclick="document.getElementById('prompts-overlay').classList.add('hidden')" style="position: absolute; top: 12px; right: 15px; background: transparent; border: none; color: var(--text-mut); font-size: 1.5rem; cursor: pointer; line-height: 1;">×</button>
            <div style="font-size: 0.9rem; color: var(--text-main); font-weight: bold; margin-bottom: 12px; border-bottom: 1px dashed var(--border); padding-bottom: 8px; display: flex; align-items: center; gap: 8px;">
                <span style="color: var(--alert); font-size: 0.7rem;">🔴</span> SPOKEN COMMANDS
            </div>
            <div style="font-size: 0.65rem; color: var(--text-dim); margin-bottom: 18px; line-height: 1.5;">
                Speak naturally to your AI Co-Pilot. You are the conductor; the AI is your live audio engine. Try saying:
            </div>
            <div style="margin-bottom: 12px;">
                <div class="prompt-category">🔥 The Mainstage Drop</div>
                <div class="prompt-example">"Build it up and drop a massive techno bassline!"</div>
                <div class="prompt-example">"Go crazy! Give me fast hi-hats at 150 BPM."</div>
            </div>
            <div style="margin-bottom: 12px;">
                <div class="prompt-category">🎤 Stem Matrix (Vocals/Melodies)</div>
                <div class="prompt-example">"Generate a female vocal singing 'Lens DNA is the future'."</div>
            </div>
            <div style="margin-bottom: 5px;">
                <div class="prompt-category">⏱️ Timing Strategy</div>
                <div style="font-size: 0.65rem; color: var(--text-dim); background: var(--msg-bg); border: 1px dashed var(--border); padding: 8px; border-radius: 4px; line-height: 1.4;">
                    Test ideas with <strong>T=8</strong> (8 seconds) first to check composition. Command full tracks like <strong>T=180</strong> once perfected.
                </div>
            </div>
        </div>

        <div class="top-bar mono">
            <button id="hamburgerBtn" class="hamburger">☰</button>
            <div class="status-pill">
                <span id="timer-display" style="font-weight:bold;">09:00</span>
                <span style="color:var(--border);">|</span>
                <span id="status" style="color:var(--text-mut);">STANDBY</span>
            </div>
            <div style="display: flex; gap: 10px; align-items: center;">
                <button id="btn-minimize-ui" class="record-btn-top" style="background: rgba(0, 229, 255, 0.1); border-color: var(--cyan); color: var(--cyan);" title="Toggle UI">
                    👁️ HUD
                </button>
                <button id="btn-record" class="record-btn-top">
                    <span class="brand-dot" style="background:var(--alert); box-shadow:none;"></span>
                    <span id="record-text-main">RECORD</span>
                </button>
            </div>
        </div>

        <div id="chat-history">
            <div class="msg-row msg-ai">
                <div class="msg-sender">SYSTEM</div>
                <div class="msg-content">
                    <strong>LensDNA Sovereign Optic Stack Ready.</strong><br>
                    Configure your keys in the sidebar, then hit CONNECT AI to establish the neural uplink.
                </div>
            </div>
        </div>

        <div id="dj-matrix-panel" class="hidden mono">
            <div class="dj-header">
                <div style="display:flex; align-items:center; gap:15px; flex-wrap:wrap;">
                    <span style="color:#b000ff; font-weight:bold; font-size:1rem;">🎛️ 8-CHANNEL STEM MATRIX</span>
                    <div style="display:flex; gap:5px;">
                        <button id="btn-prev-preset-matrix" class="btn-clear" style="background:rgba(176,0,255,0.1); border:1px dashed #b000ff; color:#b000ff; padding:4px 12px; font-size:0.65rem; transition:0.2s;" title="Previous Preset">⏮ PREV</button>
                        <button id="btn-next-preset-matrix" class="btn-clear" style="background:rgba(176,0,255,0.1); border:1px dashed #b000ff; color:#b000ff; padding:4px 12px; font-size:0.65rem; transition:0.2s;" title="Next Preset">NEXT ⏭</button>
                    </div>
                </div>
                <button id="btn-close-matrix" style="background:none;border:none;color:#fff;cursor:pointer;font-size:1.5rem;line-height:1;">×</button>
            </div>
            <div class="dj-channels" id="channels-container"></div>
        
        <div style="display:flex; flex-wrap:wrap; gap:15px; margin-top:10px; padding:12px; background:rgba(0,0,0,0.3); border-radius:8px; border:1px solid rgba(176,0,255,0.3);">
            <div style="flex:1; min-width:100px; display:flex; flex-direction:column; gap:5px;">
                <label style="color:#b000ff; font-size:0.65rem; font-weight:bold; text-transform:uppercase;">Density (Smooth → Punchy)</label>
                <input type="range" id="lyriaDensity" min="0" max="100" value="80" style="accent-color:#00ff41; cursor:pointer;">
            </div>
            <div style="flex:1; min-width:100px; display:flex; flex-direction:column; gap:5px;">
                <label style="color:#b000ff; font-size:0.65rem; font-weight:bold; text-transform:uppercase;">Brightness (Dark → Bright)</label>
                <input type="range" id="lyriaBrightness" min="0" max="100" value="70" style="accent-color:#00e5ff; cursor:pointer;">
            </div>
            <div style="flex:1; min-width:100px; display:flex; flex-direction:column; gap:5px;">
                <label style="color:#b000ff; font-size:0.65rem; font-weight:bold; text-transform:uppercase;">Chaos (Repetitive → Random)</label>
                <input type="range" id="lyriaChaos" min="0" max="100" value="30" style="accent-color:#ff00ea; cursor:pointer;">
            </div>
            <div style="display:flex; align-items:center; gap:8px; padding-top:5px;">
                <input type="checkbox" id="lyriaSeamless" checked style="accent-color:#00ff41; width:18px; height:18px; cursor:pointer;">
                <label style="color:#00ff41; font-size:0.75rem; font-weight:bold; text-transform:uppercase;">Seamless Loop</label>
            </div>
        </div>
        
        <div style="display:flex; justify-content:space-between; margin-top:15px; align-items:center; flex-wrap:wrap; gap:10px;">
            <button id="btn-add-channel" class="btn-clear" style="border:1px dashed #b000ff; color:#b000ff; background:none;">+ ADD CH (0/8)</button>
                <div style="display:flex; gap:10px; align-items:center;">
                    <span style="color:#888; font-size:0.7rem;">DUR:</span>
                    <input type="number" id="lyriaDur" class="key-input" value="120" placeholder="Sec" style="width:70px; padding:8px;">
                    <span style="color:#888; font-size:0.7rem;">BPM:</span>
                    <input type="number" id="lyriaBpm" class="key-input" value="138" placeholder="BPM" style="width:70px; padding:8px;">
                </div>
                <button id="btn-lyria-gen" class="btn-clear" style="background:#b000ff; color:#fff; border:none; padding:10px 20px; font-size:0.8rem;">SYNTHESIZE AUDIO</button>
            </div>
        </div>

        <div class="input-wrapper">
            <div class="input-box">
                <input type="file" id="file-upload" hidden multiple>
                <button id="btn-ingest" style="display:none;"></button>

                <button class="action-btn" title="Upload Audio/Doc" onclick="document.getElementById('file-upload').click()">📎</button>
                <button id="btn-screen" class="action-btn" title="Share Screen">💻</button>
                <button id="btn-flip" class="action-btn" title="Flip Camera">📷</button>
                
                <textarea id="manualInject" rows="1" placeholder="Command the AI, or drop files here..."></textarea>
                
                <button id="btn-mic" class="hero-mic-btn mono">
                    <div class="indicator"></div>
                    <span class="text">MIC OFF</span>
                </button>
                
                <button id="btn-lens" class="action-btn" title="Force OCR Vision Scan" style="color: var(--cyan);">👁️</button>
                
                <button id="btn-send-manual" class="btn-send" title="Send Command">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg>
                </button>
            </div>
        </div>
    </div>

</div>

<script type="module">
import '/static/ar_engine.js';

if (localStorage.getItem('geminiPromoDismissed') === 'true') {
    const promo = document.getElementById('geminiPromoBox');
    if (promo) promo.style.display = 'none';
}

const PROVIDER = "{{ provider }}";
const DOMAIN = "{{ domain }}";
const USE_CONTEXT = "{{ use_context }}";
const UPLINK_CLEARANCE = "coDe7777"; 
const SESSION_LIMIT_SEC = 540;

const elements = { 
    geminiInput: document.getElementById("geminiKey"),
    grokInput: document.getElementById("grokKey"),
    openaiInput: document.getElementById("openaiKey"),
    clearKeysBtn: document.getElementById("clearKeysBtn"),
    sidebar: document.getElementById("sidebar"), 
    hamburgerBtn: document.getElementById("hamburgerBtn"),
    closeSidebarBtn: document.getElementById("closeSidebar"),
    toggleSidebarBtn: document.getElementById("toggleSidebarBtn"),
    video: document.getElementById("video-feed"), 
    mainContainer: document.getElementById("main-stage"),
    btn: document.getElementById("btn-connect"), 
    btnText: document.getElementById("btn-text"), 
    connDot: document.getElementById("conn-dot"),
    screenBtn: document.getElementById("btn-screen"), 
    flipBtn: document.getElementById("btn-flip"), 
    micBtn: document.getElementById("btn-mic"), 
    lensBtn: document.getElementById("btn-lens"), 
    laserGameBtn: document.getElementById("btn-laser-game"),
    purgeBtn: document.getElementById("btn-purge"),
    recordBtn: document.getElementById("btn-record"),
    recordText: document.getElementById("record-text-main"),
    status: document.getElementById("status"), 
    timer: document.getElementById("timer-display"),
    logs: document.getElementById("logs"), 
    chat: document.getElementById("chat-history"), 
    manualInput: document.getElementById("manualInject"),
    sendManualBtn: document.getElementById("btn-send-manual"),
    fileUpload: document.getElementById("file-upload"),
    matrixPanel: document.getElementById("dj-matrix-panel"),
    btnToggleMatrix: document.getElementById("btn-toggle-matrix"),
    btnCloseMatrix: document.getElementById("btn-close-matrix")
};

let state = { socket: null, audioCtx: null, worklet: null, videoStream: null, audioStream: null, serverReady: false, nextStartTime: 0, mode: "camera", facingMode: "user", isSwapping: false, timerInterval: null, secondsLeft: SESSION_LIMIT_SEC, isSpeaking: false, lastVoiceTimestamp: 0, isGeneratingStem: false, stemTimeout: null, stemInterval: null, stemStartTime: 0, mediaRecorder: null, recordedChunks:[], recorderDest: null, micMuted: true, activeStems:[] };
let telemetry = { scanCount: 0, totalBytes: 0, startTime: Date.now() };

let engineState = { currentBPM: 138 };
window.updateBPM = function(newBPM) { engineState.currentBPM = newBPM; };
window.arState = window.arState || { active: false };

function toggleSidebar() {
    if (window.innerWidth > 900) {
        elements.sidebar.classList.toggle('collapsed');
    } else {
        elements.sidebar.classList.toggle('open');
    }
}
elements.hamburgerBtn.onclick = toggleSidebar;
if(elements.toggleSidebarBtn) elements.toggleSidebarBtn.onclick = toggleSidebar;
if(elements.closeSidebarBtn) elements.closeSidebarBtn.onclick = toggleSidebar;

elements.purgeBtn.onclick = () => {
    if(confirm("PURGE ALL EPHEMERAL DATA?\n\nThis will wipe the chat history, audio stems, and telemetry logs from your local RAM.")) {
        elements.chat.innerHTML = `<div class="msg-row msg-ai"><div class="msg-sender mono">SYSTEM</div><div class="msg-content"><strong>RAM Purged.</strong><br>All ephemeral data wiped. Ready for new input.</div></div>`;
        elements.logs.innerHTML = '<div class="log-entry"><span style="color:#555;">[SYS]</span> Telemetry Purged.</div>';
        telemetry = { scanCount: 0, totalBytes: 0, startTime: Date.now() };
        state.activeStems =[];
    }
};

elements.laserGameBtn.onclick = async () => {
    if (typeof window.toggleAR === 'function') {
        await window.toggleAR(); 
        elements.laserGameBtn.style.color = window.arState.active ? "var(--neon)" : "";
        elements.laserGameBtn.style.boxShadow = window.arState.active ? "inset 0 0 10px var(--neon)" : "none";
        
        if (window.arState.active) {
            document.getElementById('chat-history').style.display = 'none';
            document.querySelector('.input-wrapper').style.display = 'none';
            document.getElementById('btn-minimize-ui').style.opacity = '0.5';
        }
    }
};

document.getElementById('btn-minimize-ui').onclick = () => {
    const chat = document.getElementById('chat-history');
    const inputWrap = document.querySelector('.input-wrapper');
    const btn = document.getElementById('btn-minimize-ui');
    
    if (chat.style.display === 'none') {
        chat.style.display = 'flex';
        inputWrap.style.display = 'flex';
        btn.style.opacity = '1';
    } else {
        chat.style.display = 'none';
        inputWrap.style.display = 'none';
        btn.style.opacity = '0.5';
    }
};

function log(msg, isTelemetry = false) { 
    const entry = document.createElement("div"); 
    entry.className = "log-entry";
    const time = new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute:'2-digit', second:'2-digit' });
    entry.innerHTML = `<span style="color:#555;">[${time}]</span> ${msg}`; 
    elements.logs.appendChild(entry); 
    const logsContainer = document.getElementById('logs-container');
    logsContainer.scrollTop = logsContainer.scrollHeight; 
}

function updateTelemetryStats(type, sizeBytes, width, height) {
    telemetry.scanCount++; telemetry.totalBytes += sizeBytes;
    const sizeKB = Math.round(sizeBytes / 1024); const totalMB = (telemetry.totalBytes / (1024 * 1024)).toFixed(2);
    log(`TX-${telemetry.scanCount}: ${type} | ${sizeKB}KB | TOTAL: ${totalMB}MB`, true);
}

function startTimer() {
    clearInterval(state.timerInterval); state.secondsLeft = SESSION_LIMIT_SEC; updateTimerDisplay();
    state.timerInterval = setInterval(() => {
        state.secondsLeft--; updateTimerDisplay();
        if (state.secondsLeft <= 0) {
            clearInterval(state.timerInterval);
            appendChat("SYSTEM", ">> UPLINK LIMIT REACHED. SEVERING CONNECTION TO AVOID HALLUCINATIONS. <<", "sys-alert");
            disconnect();
        }
    }, 1000);
}

function updateTimerDisplay() {
    const m = Math.floor(state.secondsLeft / 60).toString().padStart(2, '0');
    const s = (state.secondsLeft % 60).toString().padStart(2, '0');
    elements.timer.innerText = `${m}:${s}`;
    if (state.secondsLeft < 30) elements.timer.style.color = "#ff3b30"; else elements.timer.style.color = "inherit";
}

function setStatus(msg, color="#00ff41") { 
    elements.status.innerText = msg; elements.status.style.color = color; 
    if(color === "#00ff41") { elements.connDot.style.background = color; elements.connDot.style.boxShadow = `0 0 10px ${color}`; } 
    else { elements.connDot.style.background = "#555"; elements.connDot.style.boxShadow = "none"; }
}

function appendChat(role, text, type = "normal") {
    if (!text) return;
    const msgDiv = document.createElement("div");
    msgDiv.className = `msg-row ${role === "USER" ? "msg-user" : "msg-ai"}`;
    let extraClass = "", senderText = role;
    if (type === "thought") { extraClass = "thought"; senderText = role + " // PROCESSING"; }
    if (type === "speech") { extraClass = "speech"; }
    if (type === "sys-alert") { extraClass = "sys-alert"; senderText = "SYSTEM OVERRIDE"; }
    msgDiv.innerHTML = `<div class="msg-sender mono">${senderText}</div><div class="msg-content ${extraClass}">${text}</div>`;
    elements.chat.appendChild(msgDiv);
    elements.chat.scrollTop = elements.chat.scrollHeight;
}

async function captureContextFrame(triggerName) {
    if (!state.serverReady || !elements.video.srcObject) return;
    const vWidth = elements.video.videoWidth; const vHeight = elements.video.videoHeight;
    const targetWidth = 1024; const scaleFactor = vWidth > targetWidth ? (targetWidth / vWidth) : 1.0;
    const finalWidth = Math.floor(vWidth * scaleFactor); const finalHeight = Math.floor(vHeight * scaleFactor);
    const canvas = document.createElement("canvas"); canvas.width = finalWidth; canvas.height = finalHeight;
    const ctx = canvas.getContext("2d");
    if (state.facingMode === "user") { ctx.translate(finalWidth, 0); ctx.scale(-1, 1); }
    ctx.drawImage(elements.video, 0, 0, finalWidth, finalHeight);
    if (window.arState && window.arState.active && window.arState.overlayCanvas) ctx.drawImage(window.arState.overlayCanvas, 0, 0, finalWidth, finalHeight);
    if (state.facingMode === "user") { ctx.setTransform(1, 0, 0, 1, 0, 0); }
    const frame = canvas.toDataURL("image/jpeg", 0.7).split(",")[1];
    const estimatedSize = Math.floor(frame.length * 0.75);
    state.socket.emit("video_frame", { data: frame, telemetry: null, trigger: triggerName });
    updateTelemetryStats("FRAME_SYNC", estimatedSize, finalWidth, finalHeight);
}

async function triggerLens() { 
    if (!state.serverReady || !elements.video.srcObject) return;
    appendChat("USER", "[LENS SCAN: HIGH FIDELITY AUDIT]"); 
    const vWidth = elements.video.videoWidth; const vHeight = elements.video.videoHeight;
    const canvas = document.createElement("canvas"); canvas.width = vWidth; canvas.height = vHeight; 
    const ctx = canvas.getContext("2d");
    if (state.facingMode === "user") { ctx.translate(vWidth, 0); ctx.scale(-1, 1); }
    ctx.drawImage(elements.video, 0, 0, vWidth, vHeight); 
    if (window.arState && window.arState.active && window.arState.overlayCanvas) ctx.drawImage(window.arState.overlayCanvas, 0, 0, vWidth, vHeight);
    if (state.facingMode === "user") { ctx.setTransform(1, 0, 0, 1, 0, 0); }
    const b64Image = canvas.toDataURL("image/jpeg", 0.95).split(",")[1]; 
    const estimatedSize = Math.floor(b64Image.length * 0.75);
    const dynamicPrompt = "PERFORM FULL ANALYSIS: 1. Extract any visible text (OCR). 2. Analyze visual energy and environment 'vibe'.";
    state.socket.emit("lens_ocr", { image: b64Image, prompt: dynamicPrompt }); 
    updateTelemetryStats("LENS_OCR", estimatedSize, vWidth, vHeight);
}

async function flipCamera() { 
    if (state.mode === "screen" || state.isSwapping) return; state.isSwapping = true; 
    if (state.videoStream) state.videoStream.getTracks().forEach(t => t.stop()); 
    state.facingMode = (state.facingMode === "user") ? "environment" : "user"; 
    window.isVideoMirrored = (state.facingMode === "user");
    elements.video.classList.toggle("mirror", state.facingMode === "user");
    await new Promise(r => setTimeout(r, 400)); 
    try { 
        const constraints = { video: { facingMode: { ideal: state.facingMode }, width: { ideal: window.innerWidth <= 900 ? 720 : 1280 }, height: { ideal: window.innerWidth <= 900 ? 1280 : 720 }, frameRate: { ideal: 30, max: 60 } } }; 
        state.videoStream = await navigator.mediaDevices.getUserMedia(constraints); 
        elements.video.srcObject = state.videoStream; 
        if(state.serverReady) setTimeout(() => captureContextFrame("CAM_FLIP"), 500);
    } catch(e) { } finally { state.isSwapping = false; } 
}

async function toggleScreenShare() { 
    if (state.isSwapping) return; state.isSwapping = true; 
    try { 
        if (state.mode === "camera") { 
            const newStream = await navigator.mediaDevices.getDisplayMedia({ video: true, preferCurrentTab: true }); 
            if (state.videoStream) state.videoStream.getTracks().forEach(t => t.stop()); 
            state.videoStream = newStream; state.mode = "screen"; elements.video.classList.remove("mirror"); 
        } else { 
            const newStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: state.facingMode, width: { ideal: window.innerWidth <= 900 ? 720 : 1280 }, height: { ideal: window.innerWidth <= 900 ? 1280 : 720 }, frameRate: { ideal: 30, max: 60 } } }); 
            if (state.videoStream) state.videoStream.getTracks().forEach(t => t.stop()); 
            state.videoStream = newStream; state.mode = "camera"; elements.video.classList.toggle("mirror", state.facingMode === "user");
        } 
        elements.video.srcObject = state.videoStream; 
        if(state.serverReady) setTimeout(() => captureContextFrame("SCREEN_TOGGLE"), 1000);
    } catch (e) { } finally { state.isSwapping = false; } 
}

const WORKLET_CODE = `class RecorderProcessor extends AudioWorkletProcessor { constructor() { super(); this.bufferSize = 4096; this.buffer = new Float32Array(this.bufferSize); this.ptr = 0; } process(inputs) { const input = inputs[0]; if (!input || input.length === 0) return true; const channel = input[0]; for (let i = 0; i < channel.length; i++) { this.buffer[this.ptr++] = channel[i]; if (this.ptr >= this.bufferSize) { this.port.postMessage(this.buffer); this.ptr = 0; } } return true; } } registerProcessor("recorder-processor", RecorderProcessor);`;
function downsampleBuffer(buffer, sampleRate) { if (sampleRate === 16000) return buffer; const ratio = sampleRate / 16000; const result = new Float32Array(Math.round(buffer.length / ratio)); let offsetResult = 0, offsetBuffer = 0; while (offsetResult < result.length) { const nextOffsetBuffer = Math.round((offsetResult + 1) * ratio); let accum = 0, count = 0; for (let i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i++) { accum += buffer[i]; count++; } result[offsetResult] = count > 0 ? accum / count : 0; offsetResult++; offsetBuffer = nextOffsetBuffer; } return result; }
function floatTo16BitPCM(float32Arr) { const buffer = new ArrayBuffer(float32Arr.length * 2); const view = new DataView(buffer); for (let i = 0; i < float32Arr.length; i++) { let s = Math.max(-1, Math.min(1, float32Arr[i])); view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7FFF, true); } return buffer; }
function base64Encode(buffer) { let binary = ""; const bytes = new Uint8Array(buffer); for (let i = 0; i < bytes.byteLength; i++) binary += String.fromCharCode(bytes[i]); return window.btoa(binary); }

async function playAudio(b64Data) { 
    if (!state.audioCtx) return; 
    try { 
        const bin = window.atob(b64Data); const len = bin.length; const arr = new Uint8Array(len); 
        for(let i=0; i<len; i++) arr[i] = bin.charCodeAt(i); 
        const int16 = new Int16Array(arr.buffer); const float32 = new Float32Array(int16.length); 
        for(let i=0; i<int16.length; i++) float32[i] = int16[i] / 32768.0; 
        const audioBuffer = state.audioCtx.createBuffer(1, float32.length, 24000); 
        audioBuffer.getChannelData(0).set(float32); 
        const src = state.audioCtx.createBufferSource(); src.buffer = audioBuffer; 
        src.connect(state.audioCtx.destination); if (state.recorderDest) src.connect(state.recorderDest);
        const currentTime = state.audioCtx.currentTime; 
        if (state.nextStartTime < currentTime) state.nextStartTime = currentTime + 0.05; 
        src.start(state.nextStartTime); state.nextStartTime += audioBuffer.duration; 
    } catch(e) {} 
}

async function playLyriaAudioStream(b64Data) { 
    if (!state.audioCtx) return; 
    try { 
        const bin = window.atob(b64Data); const len = bin.length; const arr = new Uint8Array(len); 
        for(let i=0; i<len; i++) arr[i] = bin.charCodeAt(i); 
        const int16 = new Int16Array(arr.buffer); 
        const numFrames = int16.length / 2;
        const audioBuffer = state.audioCtx.createBuffer(2, numFrames, 48000); 
        const channel0 = audioBuffer.getChannelData(0); const channel1 = audioBuffer.getChannelData(1);
        for (let i = 0; i < numFrames; i++) { channel0[i] = int16[i * 2] / 32768.0; channel1[i] = int16[i * 2 + 1] / 32768.0; }
        const src = state.audioCtx.createBufferSource(); src.buffer = audioBuffer; 
        src.connect(state.audioCtx.destination); if (state.recorderDest) src.connect(state.recorderDest);
        const currentTime = state.audioCtx.currentTime; 
        if (window.lyriaNextStartTime === undefined || window.lyriaNextStartTime < currentTime) window.lyriaNextStartTime = currentTime + 0.05; 
        src.start(window.lyriaNextStartTime); window.lyriaNextStartTime += audioBuffer.duration; 
    } catch(e) { } 
}

async function startLocalMedia() {
    if (state.videoStream) return;
    try {
        state.audioStream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 } });
        state.videoStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: state.facingMode, width: { ideal: window.innerWidth <= 900 ? 720 : 1280 }, height: { ideal: window.innerWidth <= 900 ? 1280 : 720 }, frameRate: { ideal: 30, max: 60 } } });
        elements.video.srcObject = state.videoStream; await elements.video.play();
        state.audioCtx = new (window.AudioContext || window.webkitAudioContext)(); 
        if (state.audioCtx.state === "suspended") await state.audioCtx.resume();
        state.recorderDest = state.audioCtx.createMediaStreamDestination();
        const blob = new Blob([WORKLET_CODE], { type: "application/javascript" }); 
        await state.audioCtx.audioWorklet.addModule(URL.createObjectURL(blob));
        const source = state.audioCtx.createMediaStreamSource(state.audioStream); 
        source.connect(state.recorderDest);
        state.worklet = new AudioWorkletNode(state.audioCtx, "recorder-processor"); 
        source.connect(state.worklet);
        
        state.micMuted = false;
        state.audioStream.getAudioTracks()[0].enabled = true;
        
        elements.micBtn.classList.add("active");
        elements.micBtn.querySelector(".text").innerText = "MIC ON";
        
        log("Local Hardware Engines Initialized.");
    } catch(err) {
        log("HARDWARE INIT FAILED: " + err.message);
        appendChat("SYSTEM", "Camera/Mic access denied. Please grant permissions.", "sys-alert");
    }
}

async function connect() {
    let geminiKey = elements.geminiInput.value.trim(); let grokKey = elements.grokInput.value.trim(); let openaiKey = elements.openaiInput.value.trim();
    if (geminiKey) localStorage.setItem("enigma_gemini_key", geminiKey); if (grokKey) localStorage.setItem("enigma_grok_key", grokKey); if (openaiKey) localStorage.setItem("enigma_openai_key", openaiKey);

    let activeKey = "";
    if (PROVIDER === "grok") activeKey = grokKey;
    else if (PROVIDER === "openai") activeKey = openaiKey;
    else activeKey = geminiKey;

    elements.btn.disabled = true; setStatus("INIT...", "yellow");
    await startLocalMedia();

    if (!activeKey) { elements.btn.disabled = false; elements.btn.classList.remove("active"); elements.btnText.innerText = "CONNECT AI"; return; }

    setStatus("LINKING", "yellow");
    try {
        state.nextStartTime = 0; state.isSpeaking = false; state.lastVoiceTimestamp = 0;
        state.socket = io("/live", { query: { provider: PROVIDER, domain: DOMAIN, use_context: USE_CONTEXT, clearance: UPLINK_CLEARANCE, sovereign_key: activeKey }, transports: ["websocket"], forceNew: true });

        state.socket.on('new_generative_stem', (data) => {
            state.isGeneratingStem = false; clearTimeout(state.stemTimeout); if (state.stemInterval) clearInterval(state.stemInterval);
            const btnLyria = document.getElementById('btn-lyria-gen');
            if (btnLyria) { btnLyria.innerText = "SYNTHESIZE AUDIO"; btnLyria.style.background = "rgba(176,0,255,0.1)"; }
            
            const byteCharacters = atob(data.b64_wav); const byteArray = new Uint8Array(byteCharacters.length);
            for (let i = 0; i < byteCharacters.length; i++) byteArray[i] = byteCharacters.charCodeAt(i);
            const blob = new Blob([byteArray], { type: 'audio/wav' }); const audioDataUrl = URL.createObjectURL(blob); 
            const trackId = "stem_" + Date.now();
            
            const stemHtml = `
                <div style="background:var(--panel-bg); border:1px solid var(--border); border-top:3px solid #b000ff; border-radius:12px; padding:20px; width:100%; box-sizing:border-box; box-shadow:0 10px 30px rgba(0,0,0,0.5);">
                    <div style="display:flex; justify-content:space-between; color:#b000ff; font-size:0.8rem; font-weight:bold; margin-bottom:15px; font-family:'Share Tech Mono', monospace;">
                        <span>🎛️ STEM MATRIX RENDERED</span>
                        <span>${data.bpm} BPM</span>
                    </div>
                    <div style="font-size:0.85rem; color:var(--text-main); margin-bottom:15px; font-style:italic;">"${data.description}"</div>
                    <audio id="${trackId}" src="${audioDataUrl}" controls style="width:100%; height:40px; outline:none; margin-bottom:15px; border-radius:6px;"></audio>
                    <div style="display:flex; gap:10px;">
                        <button onclick="const a = document.getElementById('${trackId}'); a.loop = !a.loop; this.style.background = a.loop ? 'var(--neon)' : 'transparent'; this.style.color = a.loop ? '#000' : 'var(--neon)';"
                                style="flex:1; padding:10px; border:1px solid var(--neon); background:transparent; color:var(--neon); border-radius:6px; cursor:pointer; font-family:'Share Tech Mono', monospace; font-size:0.8rem; font-weight:bold; transition:0.2s;">
                            🔁 LOOP
                        </button>
                        <a href="${audioDataUrl}" download="Sovereign_Stem_${data.bpm}BPM_${trackId}.wav" 
                           style="flex:1; padding:10px; text-align:center; background:#b000ff; color:#fff; text-decoration:none; font-weight:bold; border-radius:6px; font-size:0.8rem; font-family:'Share Tech Mono', monospace;">
                           ⬇️ SAVE .WAV
                        </a>
                    </div>
                </div>
            `;
            appendChat("SYSTEM", stemHtml, "speech");

            state.activeStems.push(trackId);
            if (state.activeStems.length > 3) {
                const oldestTrackId = state.activeStems.shift(); // Get the oldest
                const oldAudioEl = document.getElementById(oldestTrackId);
                if (oldAudioEl) {
                    const msgRow = oldAudioEl.closest('.msg-row');
                    if (msgRow) msgRow.remove(); // Wipe oldest track from chat/RAM completely
                }
            }

            setTimeout(() => {
                const audioEl = document.getElementById(trackId);
                if (audioEl && state.audioCtx) {
                    try {
                        if (state.audioCtx.state === 'suspended') state.audioCtx.resume();
                        if (!audioEl.sourceNode) {
                            audioEl.sourceNode = state.audioCtx.createMediaElementSource(audioEl);
                            audioEl.sourceNode.connect(state.audioCtx.destination); 
                            if (state.recorderDest) audioEl.sourceNode.connect(state.recorderDest);
                        }
                        audioEl.volume = 0.9; audioEl.play().catch(e => { });
                    } catch(err) {}
                }
            }, 150); 
        });

        state.socket.on('lyria_audio_stream_chunk', (data) => {
            if (state.audioCtx && state.audioCtx.state === "suspended") state.audioCtx.resume();
            playLyriaAudioStream(data.data);
        });
        
        state.socket.on("connect_error", (err) => { log("SOCK_ERR: " + err.message); setStatus("CONN FAIL", "red"); elements.btn.disabled = false; elements.btnText.innerText = "CONNECT AI"; });
        
        state.socket.on("connect", () => {
            state.serverReady = true; setStatus("SECURED", "#00ff41"); elements.btnText.innerText = "DISCONNECT AI"; elements.btn.classList.add("active"); elements.btn.disabled = false; elements.lensBtn.disabled = false;
            startTimer();
            setTimeout(() => { captureContextFrame("INITIAL_RECON"); }, 1500);
            
            if(window.innerWidth < 900) elements.sidebar.classList.remove('open');
            
            if (state.worklet) {
                state.worklet.port.onmessage = (e) => { 
                    if (state.serverReady && !state.micMuted) { 
                        const float32 = e.data; let sum = 0;
                        for (let i = 0; i < float32.length; i += 4) sum += float32[i] * float32[i]; 
                        const rms = Math.sqrt(sum / (float32.length / 4));
                        if (rms > 0.05) {
                            state.lastVoiceTimestamp = Date.now();
                            if (!state.isSpeaking) { state.isSpeaking = true; captureContextFrame("VOICE_ACTIVE"); }
                        }
                        if (state.isSpeaking && (Date.now() - state.lastVoiceTimestamp > 3000)) state.isSpeaking = false;
                        const audioData = base64Encode(floatTo16BitPCM(downsampleBuffer(e.data, state.audioCtx.sampleRate))); 
                        state.socket.emit("audio_chunk", { data: audioData }); 
                    } 
                };
            }
        });

        state.socket.on("force_disconnect", () => { appendChat("SYSTEM", "AI Uplink Severed by Server (Timeout).", "sys-alert"); disconnect(); });

        state.socket.on("message", (rawMsg) => {
            let msg = rawMsg;
            if (typeof rawMsg === "string") { try { msg = JSON.parse(rawMsg); } catch(e) { return; } }
            
            if (msg.asset_html) {
                if (!msg.asset_html.includes("<img")) return; 
                const wrapper = document.createElement("div"); wrapper.className = "msg-row msg-asset"; 
                wrapper.innerHTML = `<div class="msg-sender mono">SYSTEM [ASSET SECURED]</div><div class="msg-content" style="background:transparent; border:none; padding:0; box-shadow:none;">${msg.asset_html}</div>`;
                elements.chat.appendChild(wrapper); elements.chat.scrollTop = elements.chat.scrollHeight; return; 
            }

            if (msg.type === "sys-alert") {
                appendChat("SYSTEM", msg.text, "sys-alert");
                return;
            }

            if (msg.serverContent?.modelTurn?.parts) { msg.serverContent.modelTurn.parts.forEach(p => { if (p.inlineData && p.inlineData.data) { playAudio(p.inlineData.data); } }); }
            if (msg.type === "response.audio.delta" || msg.type === "audio_delta") { playAudio(msg.delta || msg.data); }
            
            let textChunks =[];
            const addText = (t) => { if (t && typeof t === "string" && t.trim().length > 0) textChunks.push(t); };
            if (msg.serverContent?.outputTranscription?.text) addText(msg.serverContent.outputTranscription.text);
            if (msg.serverContent?.output_transcription?.text) addText(msg.serverContent.output_transcription.text);
            if (msg.serverContent?.modelTurn?.parts) { msg.serverContent.modelTurn.parts.forEach(p => { if (p.text) addText(p.text); }); }
            if (msg.transcript) addText(msg.transcript);
            if (msg.text) addText(msg.text);
            
            if (msg.serverContent?.modelTurn?.parts) { 
                msg.serverContent.modelTurn.parts.forEach(p => { 
                    if (p.inlineData && p.inlineData.mimeType.startsWith('image/')) { 
                        state.socket.emit("upload_promo_asset", { data: p.inlineData.data, mime: p.inlineData.mimeType });
                    } 
                }); 
            }
            
            textChunks.forEach(textChunk => {
                const isThought = textChunk.startsWith("**") || textChunk.startsWith("Thinking Process:");
                
                let chatChildren = Array.from(elements.chat.children);
                let lastMsg = chatChildren.reverse().find(el => el.classList.contains("msg-ai"));
                let lastContent = lastMsg ? lastMsg.querySelector(".msg-content") : null;
                const lastIsThought = lastContent ? lastContent.classList.contains("thought") : false;
                
                if (lastContent && lastContent.textContent.includes(textChunk)) return;

                if (!lastMsg || (isThought !== lastIsThought)) { 
                    const msgDiv = document.createElement("div"); msgDiv.className = "msg-row msg-ai";
                    let extraClass = isThought ? "thought" : "";
                    let senderText = isThought ? "AI // PROCESSING" : "AI";
                    msgDiv.innerHTML = `<div class="msg-sender mono">${senderText}</div><div class="msg-content ${extraClass}" data-raw=""></div>`;
                    elements.chat.appendChild(msgDiv); lastMsg = msgDiv; lastContent = msgDiv.querySelector(".msg-content");
                }

                let raw = lastContent.getAttribute("data-raw") || ""; raw += textChunk; lastContent.setAttribute("data-raw", raw);

                const stemRegex = /\[GENERATE_STEM:\s*([^\]]+)\]/g;
                let stemMatch;
                while ((stemMatch = stemRegex.exec(raw)) !== null) {
                    let stemStr = stemMatch[1];
                    let tagId = "stem_executed_" + stemStr.replace(/[^a-zA-Z0-9]/g, '');
                    if (lastContent.getAttribute(tagId) !== "true") {
                        lastContent.setAttribute(tagId, "true");
                        if (!state.isGeneratingStem) {
                            state.isGeneratingStem = true; clearTimeout(state.stemTimeout); if (state.stemInterval) clearInterval(state.stemInterval);
                            state.stemStartTime = Date.now();
                            state.stemTimeout = setTimeout(() => { state.isGeneratingStem = false; if (state.stemInterval) clearInterval(state.stemInterval); }, 600000); 
                            
                            const btnLyria = document.getElementById('btn-lyria-gen');
                            if (btnLyria) { btnLyria.innerText = "🛑 STOP & RENDER"; btnLyria.style.background = "var(--alert)"; }
                            
                            state.socket.emit("trigger_stem_generation", { prompt: stemStr });
                        } else {
                            appendChat("SYSTEM", "Interrupting current track and queueing new generation...", "sys-alert");
                            state.socket.emit("cancel_stem");
                            setTimeout(() => {
                                state.socket.emit("trigger_stem_generation", { prompt: stemStr });
                            }, 1500);
                        }
                    }
                }

                let displayHtml = raw.replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\\n/g, "<br>");
                displayHtml = displayHtml.replace(/\[GENERATE_STEM:\s*([^\]]+)\]/g, 
                    '<br><span style="color:#b000ff; border:1px dashed #b000ff; background:rgba(176, 0, 255, 0.1); padding:6px 10px; border-radius:6px; font-size:0.8rem; font-weight:bold; letter-spacing:1px; display:inline-block; margin-top:10px; font-family:\'Share Tech Mono\', monospace;">🎧 LYRIA SYNTHESIZING: $1</span><br>');

                lastContent.innerHTML = displayHtml; 
                elements.chat.scrollTop = elements.chat.scrollHeight;
            });
        });

        state.socket.on("disconnect", () => { disconnect(); });
    } catch(e) { disconnect(); }
}

async function disconnect() {
    setStatus("LOCAL ONLY", "#00ccff"); elements.btnText.innerText = "CONNECT AI"; elements.btn.classList.remove("active"); state.serverReady = false;
    
    state.micMuted = true;
    if (state.audioStream && state.audioStream.getAudioTracks().length > 0) state.audioStream.getAudioTracks()[0].enabled = false;
    elements.micBtn.classList.remove("active");
    elements.micBtn.querySelector(".text").innerText = "MIC OFF";

    clearInterval(state.timerInterval); if (state.stemInterval) clearInterval(state.stemInterval);
    if (state.socket) { state.socket.disconnect(); state.socket = null; }
    elements.lensBtn.disabled = true;
    
    if (state.mediaRecorder && state.mediaRecorder.state !== "inactive") state.mediaRecorder.stop();
    elements.recordText.innerText = "RECORD"; elements.recordBtn.style.color = "var(--alert)"; elements.btn.disabled = false;
}

elements.btn.onclick = async () => { if (state.serverReady) { await disconnect(); } else { connect(); } };

elements.clearKeysBtn.onclick = () => {
    if(confirm("UNLINK SOVEREIGN KEYS?\n\nThis will remove your API keys from local memory.")) {
        localStorage.removeItem("enigma_gemini_key"); localStorage.removeItem("enigma_grok_key"); localStorage.removeItem("enigma_openai_key");
        elements.geminiInput.value = ""; elements.grokInput.value = ""; elements.openaiInput.value = "";
    }
};

elements.screenBtn.onclick = toggleScreenShare; 
elements.flipBtn.onclick = flipCamera; 
elements.lensBtn.onclick = triggerLens; 

elements.micBtn.onclick = () => {
    if (!state.audioStream) return;
    const audioTracks = state.audioStream.getAudioTracks();
    if (audioTracks.length > 0) {
        state.micMuted = !state.micMuted;
        audioTracks[0].enabled = !state.micMuted;
        
        if (state.micMuted) {
            elements.micBtn.classList.remove("active");
            elements.micBtn.querySelector(".text").innerText = "MIC OFF";
        } else {
            elements.micBtn.classList.add("active");
            elements.micBtn.querySelector(".text").innerText = "MIC ON";
        }
    }
}; 

function sendManualInput() {
    const t = elements.manualInput.value.trim(); 
    if(t && state.serverReady) { 
        captureContextFrame("USER_INPUT");
        appendChat("USER", t); 
        elements.manualInput.value = ""; 
        state.socket.emit("user_message", { text: t }); 
    }
}
elements.sendManualBtn.onclick = sendManualInput;
elements.manualInput.addEventListener("keydown", (e) => { 
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendManualInput(); } 
});

const dropZone = elements.mainContainer;
dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('drag-active'); });
dropZone.addEventListener('dragleave', (e) => { e.preventDefault(); dropZone.classList.remove('drag-active'); });

function handleFiles(files) {
    if (files.length === 0) return;
    Array.from(files).forEach(file => {
        appendChat("USER", `[UPLOADING: ${file.name}...]`, "sys-alert");
        const reader = new FileReader();
        reader.onload = async function(evt) {
            const rawData = evt.target.result; 
            if (state.socket && state.serverReady) {
                if (file.type.startsWith('audio/') || file.name.toLowerCase().match(/\.(wav|mp3|m4a|ogg)$/)) {
                    try {
                        if (!state.audioCtx) state.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                        if (state.audioCtx.state === "suspended") await state.audioCtx.resume();
                        appendChat("SYSTEM", `Decoding and resampling audio: ${file.name}...`, "sys-alert");
                        
                        const audioBuffer = await state.audioCtx.decodeAudioData(rawData);
                        const duration = Math.min(audioBuffer.duration, 30); 
                        const offlineCtx = new OfflineAudioContext(1, duration * 16000, 16000);
                        const source = offlineCtx.createBufferSource();
                        source.buffer = audioBuffer;
                        source.connect(offlineCtx.destination);
                        source.start();
                        
                        const renderedBuffer = await offlineCtx.startRendering();
                        const float32Data = renderedBuffer.getChannelData(0);
                        const sampleRate = 16000;
                        for (let i = 0; i < float32Data.length; i += sampleRate) {
                            const chunk = float32Data.subarray(i, i + sampleRate);
                            const pcm16Data = floatTo16BitPCM(chunk);
                            const b64Data = base64Encode(pcm16Data);
                            state.socket.emit("audio_chunk", { data: b64Data });
                        }
                        setTimeout(() => {
                            const prompt = `I just uploaded a track snippet named ${file.name}. Listen to the high-fidelity audio stream I just transmitted, analyze the vibe, and tell me exactly what stem, synth, or beat I should generate to add to it.`;
                            appendChat("USER", prompt);
                            state.socket.emit("user_message", { text: prompt });
                        }, 500);
                    } catch (err) { appendChat("SYSTEM", `Failed to process audio: ${err.message}`, "sys-alert"); }
                } else {
                    state.socket.emit('process_document', { filename: file.name, data: rawData });
                }
            }
        };
        reader.readAsArrayBuffer(file);
    });
}

dropZone.addEventListener('drop', (e) => {
    e.preventDefault(); dropZone.classList.remove('drag-active');
    handleFiles(e.dataTransfer.files);
});

elements.fileUpload.addEventListener('change', (e) => {
    handleFiles(e.target.files);
});

elements.recordBtn.onclick = async () => {
    if (!state.mediaRecorder || state.mediaRecorder.state === "inactive") {
        if (!state.videoStream || !state.audioCtx) return;
        
        let videoTracks =[];
        let displayStream = null;

        try {
            if (navigator.mediaDevices.getDisplayMedia) {
                displayStream = await navigator.mediaDevices.getDisplayMedia({ video: { displaySurface: 'browser' }, preferCurrentTab: true, audio: false });
                videoTracks = displayStream.getVideoTracks();
            } else { throw new Error("Not supported"); }
        } catch (err) { videoTracks = state.videoStream.getVideoTracks(); }

        if (videoTracks.length === 0) return;
        
        if (!state.recorderDest) { 
            state.recorderDest = state.audioCtx.createMediaStreamDestination(); 
            const source = state.audioCtx.createMediaStreamSource(state.audioStream); 
            source.connect(state.recorderDest); 
        }
        const audioTracks = state.recorderDest.stream.getAudioTracks();
        const combinedStream = new MediaStream([...videoTracks, ...audioTracks]);
        
        let mimeType = 'video/webm;codecs=vp8,opus';
        if (!MediaRecorder.isTypeSupported(mimeType)) { mimeType = 'video/webm'; if (!MediaRecorder.isTypeSupported(mimeType)) mimeType = 'video/mp4'; }
        
        try { state.mediaRecorder = new MediaRecorder(combinedStream, mimeType ? { mimeType } : undefined); } 
        catch (e) { state.mediaRecorder = new MediaRecorder(combinedStream); }
        
        state.recordedChunks =[];
        state.mediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) state.recordedChunks.push(e.data); };
        state.mediaRecorder.onstop = () => {
            if (displayStream) displayStream.getTracks().forEach(track => track.stop());
            const finalMime = state.mediaRecorder.mimeType || 'video/mp4';
            const blob = new Blob(state.recordedChunks, { type: finalMime });
            const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.style.display = 'none'; a.href = url;
            let ext = finalMime.includes("webm") ? "webm" : "mp4";
            a.download = `LensDNA_Performance_${Date.now()}.${ext}`; document.body.appendChild(a); a.click();
            setTimeout(() => { document.body.removeChild(a); window.URL.revokeObjectURL(url); }, 100);
            
            elements.recordText.innerText = "RECORD"; elements.recordBtn.style.color = "var(--alert)"; elements.recordBtn.style.background = "rgba(255,59,48,0.1)";
        };
        if (displayStream && videoTracks[0]) { videoTracks[0].onended = () => { if (state.mediaRecorder && state.mediaRecorder.state !== "inactive") state.mediaRecorder.stop(); }; }

        state.mediaRecorder.start();
        elements.recordText.innerText = "STOP REC"; elements.recordBtn.style.color = "var(--neon)"; elements.recordBtn.style.background = "rgba(0,255,65,0.1)";
    } else { state.mediaRecorder.stop(); }
};

const MAX_CHANNELS = 8;
const channelsContainer = document.getElementById('channels-container');
const btnAddChannel = document.getElementById('btn-add-channel');
let activeChannels = 0;
const chDefaults =[
    { text: "filthy techno bass", color: "#00ff41", weight: 1.0 }, { text: "lush ambient strings", color: "#00e5ff", weight: 0.0 },
    { text: "female vocal hook", color: "#b000ff", weight: 0.0 }, { text: "acid synth arp", color: "#ff00aa", weight: 0.0 },
    { text: "tribal percussion", color: "#fadc00", weight: 0.0 }, { text: "ethereal pad", color: "#ff3b30", weight: 0.0 },
    { text: "upfront, dry, crystal clear female pop lead vocal. Lyrics: 'type your lyrics here'", color: "#ff00ea", weight: 0.0 }, { text: "upfront, dry, resonant baritone male soul lead vocal. Lyrics: 'type your lyrics here'", color: "#0055ff", weight: 0.0 }
];

function injectChannel() {
    if (activeChannels >= MAX_CHANNELS) return;
    const ch = chDefaults[activeChannels]; 
    activeChannels++;
    
    const currentId = activeChannels; 
    
    const col = document.createElement('div'); 
    col.className = "dj-channel";
    col.innerHTML = `
        <input type="text" id="ch${currentId}-prompt" class="key-input" value="${ch.text}" style="margin-bottom: 5px; text-align: center; padding: 4px; font-size: 0.55rem; background: var(--input-bg); color: var(--text-main);">
        <input type="range" id="ch${currentId}-weight" min="0" max="2" step="0.1" value="${ch.weight}" style="writing-mode: vertical-lr; direction: rtl; flex: 1; height: 80px; width: 15px; accent-color: ${ch.color}; cursor: pointer;">
        <span id="ch${currentId}-val" style="font-size: 0.65rem; font-weight: bold; margin-top: 5px; color: ${ch.color};">${ch.weight.toFixed(1)}</span>
    `;
    channelsContainer.appendChild(col);
    
    const weightSlider = col.querySelector(`#ch${currentId}-weight`);
    const valDisplay = col.querySelector(`#ch${currentId}-val`);
    
    weightSlider.addEventListener('input', (e) => {
        valDisplay.innerText = parseFloat(e.target.value).toFixed(1);
    });
    
    if (btnAddChannel) { 
        btnAddChannel.innerText = `+ ADD CH (${activeChannels}/${MAX_CHANNELS})`; 
        if (activeChannels >= MAX_CHANNELS) { 
            btnAddChannel.style.opacity = "0.5"; 
            btnAddChannel.style.cursor = "not-allowed"; 
        } 
    }
}
if (channelsContainer) { injectChannel(); injectChannel(); injectChannel(); if (btnAddChannel) btnAddChannel.onclick = injectChannel; }

const djPresets =[
    { name: "Inst: Mainstage Festival Progressive House (2026 Anthem)", bpm: 128, dur: 16, density: 98, brightness: 98, chaos: 32, seamless: true, channels:[
        { text: "massive punchy four-on-the-floor festival kick with sidechain pump", weight: 1.7, color: "#00ff41" }, 
        { text: "filthy rolling sub bass with big-room bounce and pop hook energy", weight: 1.4, color: "#00e5ff" }, 
        { text: "crisp 909 shakers, claps, and explosive building drum rolls", weight: 1.3, color: "#b000ff" }, 
        { text: "huge detuned supersaw lead with electrifying festival drop melody", weight: 1.8, color: "#ff00aa" }, 
        { text: "euphoric layered supersaw chords and bright uplifting piano", weight: 1.5, color: "#fadc00" }, 
        { text: "stadium riser sweeps, impacts, and massive crowd cheer fx", weight: 1.2, color: "#ff3b30" }, 
        { text: "", weight: 0.0, color: "#ff00ea" }, { text: "", weight: 0.0, color: "#0055ff" }
    ]},
    { name: "Inst: Peak-Time Tech House (TikTok & Beatport King)", bpm: 129, dur: 16, density: 92, brightness: 65, chaos: 35, seamless: true, channels:[
        { text: "groovy punchy tech-house kick with swing and sidechain", weight: 1.6, color: "#00ff41" }, 
        { text: "warm rolling sub bassline with bouncy tech-house groove", weight: 1.5, color: "#00e5ff" }, 
        { text: "crisp 909 hi-hats, driving shakers, and percussive groove", weight: 1.4, color: "#b000ff" }, 
        { text: "catchy detuned synth stabs and vocal chop hooks for TikTok", weight: 1.6, color: "#ff00aa" }, 
        { text: "melodic tech-house arpeggio and uplifting synth layers", weight: 1.7, color: "#fadc00" }, 
        { text: "subtle atmospheric pads and tension-building fx", weight: 0.9, color: "#ff3b30" }, 
        { text: "", weight: 0.0, color: "#ff00ea" }, { text: "", weight: 0.0, color: "#0055ff" }
    ]},
    { name: "Inst: Melodic Techno (Cinematic Festival Weapon)", bpm: 126, dur: 16, density: 85, brightness: 60, chaos: 28, seamless: true, channels:[
        { text: "deep punchy melodic techno kick with subtle swing", weight: 1.6, color: "#00ff41" }, 
        { text: "rolling hypnotic sub bassline with dark groove", weight: 1.4, color: "#00e5ff" }, 
        { text: "crisp driving hi-hats and intricate percussion", weight: 1.2, color: "#b000ff" }, 
        { text: "cinematic brass stabs and emotional synth melodies", weight: 1.5, color: "#ff00aa" }, 
        { text: "euphoric analog arpeggios and soaring melodic layers", weight: 1.8, color: "#fadc00" }, 
        { text: "haunting atmospheric pads and dystopian tension fx", weight: 1.1, color: "#ff3b30" }, 
        { text: "", weight: 0.0, color: "#ff00ea" }, { text: "", weight: 0.0, color: "#0055ff" }
    ]},
    { name: "Inst: Explosive Afro House (Global Viral Breakout)", bpm: 122, dur: 16, density: 95, brightness: 85, chaos: 40, seamless: true, channels:[
        { text: "deep tribal afro house kick with organic swing and punch", weight: 1.7, color: "#00ff41" }, 
        { text: "fat rolling sub bass fused with afro percussion groove", weight: 1.6, color: "#00e5ff" }, 
        { text: "shakers, log drums, and energetic tribal percussion", weight: 1.5, color: "#b000ff" }, 
        { text: "sunny melodic afro synth hooks and vocal chants", weight: 1.7, color: "#ff00aa" }, 
        { text: "warm uplifting piano and brass layers with festival energy", weight: 1.4, color: "#fadc00" }, 
        { text: "atmospheric risers, claps, and earthy impact fx", weight: 1.0, color: "#ff3b30" }, 
        { text: "", weight: 0.0, color: "#ff00ea" }, { text: "", weight: 0.0, color: "#0055ff" }
    ]},
    { name: "Inst: Viral UK Garage / Speed Garage (TikTok Rocket)", bpm: 134, dur: 8, density: 88, brightness: 90, chaos: 25, seamless: true, channels:[
        { text: "bouncy UK garage kick fused with modern bass punch", weight: 1.6, color: "#00ff41" }, 
        { text: "fat rolling garage bassline with 2-step swing", weight: 1.7, color: "#00e5ff" }, 
        { text: "crisp sped-up hi-hats and garage shakers", weight: 1.3, color: "#b000ff" }, 
        { text: "catchy chopped vocal hooks and neon synth stabs", weight: 1.8, color: "#ff00aa" }, 
        { text: "uplifting garage chords and bright melodic riffs", weight: 1.4, color: "#fadc00" }, 
        { text: "glitchy fx, risers, and TikTok-ready impact drops", weight: 1.1, color: "#ff3b30" }, 
        { text: "", weight: 0.0, color: "#ff00ea" }, { text: "", weight: 0.0, color: "#0055ff" }
    ]},
    { name: "Inst: High-Energy Drum & Bass (2026 Crossover Surge)", bpm: 174, dur: 8, density: 96, brightness: 85, chaos: 45, seamless: true, channels:[
        { text: "rolling jungle breakbeat with massive dnb kick", weight: 1.7, color: "#00ff41" }, 
        { text: "deep growling reece bass and sub pressure", weight: 1.6, color: "#00e5ff" }, 
        { text: "rapid fire amen breaks, crisp hi-hats, and snare rolls", weight: 1.5, color: "#b000ff" }, 
        { text: "euphoric liquid synth leads and neuro bass stabs", weight: 1.7, color: "#ff00aa" }, 
        { text: "uplifting orchestral strings and piano chords", weight: 1.3, color: "#fadc00" }, 
        { text: "dramatic risers, impacts, and festival drop fx", weight: 1.2, color: "#ff3b30" }, 
        { text: "", weight: 0.0, color: "#ff00ea" }, { text: "", weight: 0.0, color: "#0055ff" }
    ]},
    { name: "Inst: Future Rave / Big Room EDM (Mainstage Destroyer)", bpm: 130, dur: 16, density: 97, brightness: 92, chaos: 38, seamless: true, channels:[
        { text: "huge festival big-room kick with hard-hitting sidechain", weight: 1.7, color: "#00ff41" }, 
        { text: "massive distorted bass drop with future rave energy", weight: 1.6, color: "#00e5ff" }, 
        { text: "powerful claps, shakers, and epic drum builds", weight: 1.3, color: "#b000ff" }, 
        { text: "huge rave supersaw leads and anthemic hooks", weight: 1.8, color: "#ff00aa" }, 
        { text: "euphoric chord stabs and cinematic synth layers", weight: 1.5, color: "#fadc00" }, 
        { text: "massive laser impacts, risers, and crowd explosion fx", weight: 1.3, color: "#ff3b30" }, 
        { text: "", weight: 0.0, color: "#ff00ea" }, { text: "", weight: 0.0, color: "#0055ff" }
    ]},
    { name: "Vocal: Lens DNA Ultimate 2026 Festival Anthem", bpm: 128, dur: 16, density: 99, brightness: 100, chaos: 22, seamless: true, channels:[
        { text: "upfront, powerful, euphoric female pop anthem lead vocal. Lyrics: 'Midnight fires and endless screens, Hans Schulte built the ultimate dream! The Republic of DJs, a brand new dawn. Lens DNA, the app of all apps! Own your sound, stream it out, be the DJ you were born to be! Next generation, wild and free!'", weight: 2.3, color: "#ff00ea" },
        { text: "driving festival progressive house kick with big-room punch", weight: 1.7, color: "#00ff41" }, 
        { text: "warm thick rolling sub bass with dance-pop bounce", weight: 1.4, color: "#00e5ff" }, 
        { text: "massive euphoric supersaw chords and viral hook layers", weight: 1.9, color: "#ff00aa" }, 
        { text: "bright sparkling piano and electropop melody riffs", weight: 1.6, color: "#fadc00" }, 
        { text: "crisp 909 open hi-hats, claps, and massive drum rolls", weight: 1.4, color: "#b000ff" }, 
        { text: "stadium crowd cheering, huge risers, and TikTok drop impacts", weight: 1.3, color: "#ff3b30" }, 
        { text: "harmonized female backing vocals singing 'Next generation! Lens DNA!'", weight: 1.3, color: "#0055ff" }
    ]}
];

if (elements.btnToggleMatrix) {
    elements.btnToggleMatrix.onclick = () => {
        elements.matrixPanel.classList.remove('hidden');
        if (window.innerWidth <= 900) elements.sidebar.classList.remove('open');
    };
}

if (elements.btnCloseMatrix) {
    elements.btnCloseMatrix.onclick = () => {
        elements.matrixPanel.classList.add('hidden');
    };
}
let currentPresetIdx = -1;

function loadPreset(direction) {
    elements.matrixPanel.classList.remove('hidden');
    if (window.innerWidth <= 900) elements.sidebar.classList.remove('open');
    
    if (direction === 'next') {
        currentPresetIdx = (currentPresetIdx + 1) % djPresets.length;
    } else if (direction === 'prev') {
        currentPresetIdx = (currentPresetIdx - 1 + djPresets.length) % djPresets.length;
    }
    
    const preset = djPresets[currentPresetIdx];
    
    while (activeChannels < 8) injectChannel();
    
    for (let i = 0; i < 8; i++) {
        const textEl = document.getElementById(`ch${i+1}-prompt`); const weightEl = document.getElementById(`ch${i+1}-weight`); const valEl = document.getElementById(`ch${i+1}-val`);
        if (textEl && weightEl && valEl && preset.channels[i]) {
            const chData = preset.channels[i]; textEl.value = chData.text; weightEl.value = chData.weight; valEl.innerText = chData.weight.toFixed(1);
        }
    }
    
    document.getElementById('lyriaDur').value = preset.dur; document.getElementById('lyriaBpm').value = preset.bpm;
    
    if (preset.density !== undefined) document.getElementById('lyriaDensity').value = preset.density;
    if (preset.brightness !== undefined) document.getElementById('lyriaBrightness').value = preset.brightness;
    if (preset.chaos !== undefined) document.getElementById('lyriaChaos').value = preset.chaos;
    if (preset.seamless !== undefined) document.getElementById('lyriaSeamless').checked = preset.seamless;

    if (typeof window.updateBPM === 'function') window.updateBPM(preset.bpm);
    appendChat("SYSTEM", `🎛️ **MATRIX LOADED:** ${preset.name}[${preset.bpm} BPM / ${preset.dur}s]`, "sys-alert");
}

const btnNextPreset = document.getElementById('btn-next-preset');
if (btnNextPreset) btnNextPreset.onclick = () => loadPreset('next');

const btnPrevMatrix = document.getElementById('btn-prev-preset-matrix');
if (btnPrevMatrix) btnPrevMatrix.onclick = () => loadPreset('prev');

const btnNextMatrix = document.getElementById('btn-next-preset-matrix');
if (btnNextMatrix) btnNextMatrix.onclick = () => loadPreset('next');

const btnLyria = document.getElementById('btn-lyria-gen');

if (btnLyria) {
    btnLyria.onclick = () => {
        if (!state.serverReady) return;
        
        if (state.isGeneratingStem) {
            btnLyria.innerText = "PACKAGING AUDIO...";
            btnLyria.style.background = "var(--alert)";
            state.socket.emit("cancel_stem");
            appendChat("USER", "[MANUAL OVERRIDE]: Halting stream and packaging current audio...", "sys-alert");
            return;
        }

        const payload =[]; 
        const summaryText =[];
        
        for (let i = 1; i <= activeChannels; i++) {
            const textEl = document.getElementById(`ch${i}-prompt`); 
            const weightEl = document.getElementById(`ch${i}-weight`);
            
            if (textEl && weightEl && textEl.value) {
                const weightVal = parseFloat(weightEl.value);
                if (weightVal > 0) {
                    payload.push({ text: textEl.value, weight: weightVal });
                    summaryText.push(`${textEl.value} (${weightVal})`);
                }
            }
        }
        
        if (payload.length === 0) return;

        const density = parseInt(document.getElementById('lyriaDensity')?.value || "80", 10);
        const brightness = parseInt(document.getElementById('lyriaBrightness')?.value || "70", 10);
        const isSeamless = document.getElementById('lyriaSeamless')?.checked;

        const modifierAdjectives =[];
        if (density > 70) modifierAdjectives.push("dense, full arrangement");
        if (density < 40) modifierAdjectives.push("minimalist, sparse");
        if (brightness > 70) modifierAdjectives.push("bright, clear, polished");
        if (brightness < 40) modifierAdjectives.push("dark, muffled, lo-fi");
        if (isSeamless) modifierAdjectives.push("seamless perfect loop");

        if (modifierAdjectives.length > 0) {
            const masterPrompt = "Mastering style: " + modifierAdjectives.join(", ");
            payload.push({ text: masterPrompt, weight: 0.5 }); 
        }

        state.isGeneratingStem = true;
        btnLyria.style.background = "var(--alert)";
        btnLyria.innerText = "🛑 OPTIMIZING PROMPT...";
        
        setTimeout(() => { 
            if (state.isGeneratingStem) btnLyria.innerText = "🛑 GENERATING MUSIC..."; 
        }, 2500);
        
        setTimeout(() => { 
            if (state.isGeneratingStem) btnLyria.innerText = "🛑 RENDERING AUDIO..."; 
        }, 6500);

        const dur = parseInt(document.getElementById('lyriaDur')?.value || "120", 10); 
        const bpm = parseInt(document.getElementById('lyriaBpm')?.value || "138", 10);

        appendChat("USER", `[MATRIX TRIGGER]: Interpolating -> ${summaryText.join(' + ')} | Modifiers Applied`, "sys-alert");
        
        state.socket.emit("trigger_stem_generation", { 
            prompts: payload, 
            duration: dur, 
            bpm: bpm 
        });
    };
}

const savedGemini = localStorage.getItem("enigma_gemini_key"); const savedGrok = localStorage.getItem("enigma_grok_key"); const savedOpenAI = localStorage.getItem("enigma_openai_key");
if (savedGemini) elements.geminiInput.value = savedGemini; if (savedGrok) elements.grokInput.value = savedGrok; if (savedOpenAI) elements.openaiInput.value = savedOpenAI;

const themeBtn = document.getElementById('themeToggle');
const themes =['auto', 'dark', 'light'];
let currentTheme = localStorage.getItem('lensdna_hud_theme') || 'auto';
function applyTheme(theme) {
    if (theme === 'light') { document.documentElement.setAttribute('data-theme', 'light'); themeBtn.innerText = 'THEME ☼'; }
    else if (theme === 'dark') { document.documentElement.setAttribute('data-theme', 'dark'); themeBtn.innerText = 'THEME ☾'; }
    else {
        if (window.matchMedia('(prefers-color-scheme: light)').matches) document.documentElement.setAttribute('data-theme', 'light');
        else document.documentElement.removeAttribute('data-theme');
        themeBtn.innerText = 'THEME ◐';
    }
}
themeBtn.onclick = () => {
    let nextIndex = (themes.indexOf(currentTheme) + 1) % themes.length;
    currentTheme = themes[nextIndex]; localStorage.setItem('lensdna_hud_theme', currentTheme); applyTheme(currentTheme);
};
applyTheme(currentTheme);
</script>
</body>
</html>
"""

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <link rel="icon" type="image/png" href="/static/app-icon.png">
    <title>LensDNA | Sovereign Optic Stack</title>
    <link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Inter:wght@300;400;600;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #F8FAFC;
            --surface: rgba(255, 255, 255, 0.85);
            --surface-solid: #FFFFFF;
            --text-main: #0F172A;
            --text-muted: #64748B;
            --accent: #059669; 
            --accent-sec: #2563EB; 
            --border: #E2E8F0;
            --grid-color: rgba(15, 23, 42, 0.04);
            --danger: #DC2626;
            --glass-shadow: 0 8px 32px rgba(0, 0, 0, 0.05);
            --glow-core: rgba(5, 150, 105, 0.8);
            --glow-outer: rgba(37, 99, 235, 0.4);
        }
        @media (prefers-color-scheme: dark) {
            :root {
                --bg: #050505;
                --surface: rgba(17, 17, 17, 0.85);
                --surface-solid: #111111;
                --text-main: #F8FAFC;
                --text-muted: #94A3B8;
                --accent: #00FF41; 
                --accent-sec: #00E5FF; 
                --border: #222222;
                --grid-color: rgba(0, 255, 65, 0.06);
                --danger: #FF3B30;
                --glass-shadow: 0 8px 32px rgba(0, 255, 65, 0.08);
                --glow-core: #00FF41;
                --glow-outer: #00E5FF;
            }
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        html { scroll-behavior: smooth; }
        body {
            background-color: var(--bg); color: var(--text-main);
            font-family: 'Inter', system-ui, sans-serif;
            line-height: 1.6; overflow-x: hidden;
            transition: background-color 0.4s ease, color 0.4s ease;
        }
        .mono { font-family: 'Share Tech Mono', monospace; letter-spacing: 0.5px; }
        .grid-bg {
            position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
            background-image: linear-gradient(var(--grid-color) 1px, transparent 1px),
                              linear-gradient(90deg, var(--grid-color) 1px, transparent 1px);
            background-size: 40px 40px; z-index: -1; pointer-events: none;
            transition: 0.4s ease;
        }
        nav {
            position: fixed; top: 0; width: 100%; z-index: 1000;
            background: var(--surface); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--border); transition: 0.4s ease;
        }
        .nav-container {
            max-width: 1200px; margin: 0 auto; padding: 16px 24px;
            display: flex; justify-content: space-between; align-items: center;
        }
        .logo { display: flex; align-items: center; font-size: 1.1rem; font-weight: 600; color: var(--text-main); text-decoration: none; z-index: 1002; }
        .logo img { height: 28px; margin-right: 12px; border-radius: 6px; }
        .logo span { color: var(--accent); }
        .nav-links { display: flex; gap: 24px; }
        .nav-links a {
            color: var(--text-muted); text-decoration: none; font-size: 0.75rem; font-weight: 600;
            text-transform: uppercase; letter-spacing: 1px; transition: color 0.3s ease;
        }
        .nav-links a:hover { color: var(--accent); }
        .mobile-menu-btn {
            display: none; background: none; border: none; cursor: pointer; padding: 5px; z-index: 1002;
        }
        .mobile-menu-btn .bar {
            display: block; width: 24px; height: 2px; margin: 5px auto;
            background-color: var(--text-main); transition: all 0.3s ease-in-out;
        }
        header {
            min-height: 100vh; display: flex; flex-direction: column;
            justify-content: center; align-items: center; position: relative;
            padding: 120px 20px 40px 20px; overflow: hidden;
        }
        .lens-wrapper {
            position: relative; width: 320px; height: 320px;
            perspective: 1200px; margin-bottom: 50px;
        }
        .lens-container {
            width: 100%; height: 100%; position: absolute;
            transform-style: preserve-3d; 
            transition: transform 0.1s cubic-bezier(0.25, 0.46, 0.45, 0.94);
        }
        .ring { 
            position: absolute; border-radius: 50%; top: 50%; left: 50%;
            pointer-events: none; transform-style: preserve-3d;
        }
        .holo-ring-1 { 
            width: 140%; height: 140%; 
            border: 2px dashed var(--accent-sec); opacity: 0.4; 
            animation: spin 25s linear infinite; 
            transform: translate(-50%, -50%) translateZ(-40px);
            box-shadow: inset 0 0 20px rgba(37, 99, 235, 0.2);
        }
        .holo-ring-2 { 
            width: 110%; height: 110%; 
            border: 4px solid transparent; 
            border-top-color: var(--accent); border-bottom-color: var(--accent); 
            animation: spin-reverse 12s linear infinite; 
            transform: translate(-50%, -50%) translateZ(15px); 
            box-shadow: 0 0 30px rgba(0, 255, 65, 0.1);
            filter: drop-shadow(0 0 8px var(--accent));
        }
        .holo-ring-3 { 
            width: 85%; height: 85%; 
            border: 1px dotted var(--text-main); opacity: 0.6; 
            animation: spin 8s linear infinite; 
            transform: translate(-50%, -50%) translateZ(60px); 
        }
        .core-app-icon {
            position: absolute; width: 70%; height: 70%; 
            top: 50%; left: 50%; 
            transform: translate(-50%, -50%) translateZ(35px); 
            transform-style: preserve-3d; 
            display: flex; justify-content: center; align-items: center;
        }
        .core-app-icon img {
            width: 100%; height: 100%; position: relative; z-index: 10;
            filter: drop-shadow(0 20px 30px rgba(0,0,0,0.5)) drop-shadow(0 0 15px var(--accent));
        }
        .quantum-core-glow {
            position: absolute; width: 45%; height: 45%; 
            top: 50%; left: 50%; transform: translate(-50%, -50%); 
            background: radial-gradient(circle, var(--glow-core) 0%, var(--glow-outer) 60%, transparent 80%); 
            border-radius: 50%; filter: blur(12px); z-index: 5; 
            animation: reactor-pulse 2s infinite alternate cubic-bezier(0.4, 0, 0.2, 1);
        }
        .hud-panel {
            position: absolute; background: var(--surface); backdrop-filter: blur(8px);
            border: 1px solid var(--border); padding: 12px 16px; border-radius: 8px;
            font-size: 0.7rem; color: var(--text-muted); box-shadow: var(--glass-shadow);
            pointer-events: none; transition: 0.4s ease; z-index: 20;
        }
        .hud-left { top: 0%; left: -65%; text-align: left; border-left: 3px solid var(--accent); }
        .hud-right { bottom: 0%; right: -65%; text-align: right; border-right: 3px solid var(--accent-sec); }
        .hud-panel strong { color: var(--accent); }
        .hero-text { text-align: center; max-width: 700px; z-index: 10; position: relative; }
        h1 { font-size: 2.8rem; font-weight: 300; letter-spacing: -1px; margin-bottom: 8px; color: var(--text-main); }
        h1 strong { font-weight: 800; color: var(--accent); }
        .canvas-tagline {
            font-size: 1.1rem; font-weight: 600; color: var(--accent);
            text-transform: uppercase; letter-spacing: 2px;
            margin-bottom: 24px; text-shadow: 0 0 15px rgba(0, 255, 65, 0.3);
            display: inline-block; padding: 8px 16px;
            border: 1px solid rgba(0, 255, 65, 0.2); border-radius: 4px;
            background: rgba(0, 255, 65, 0.05);
        }
        .hero-desc { font-size: 1.05rem; color: var(--text-muted); margin-bottom: 32px; }
        .section-container { max-width: 1000px; margin: 0 auto; padding: 80px 24px; }
        .section-header { font-size: 0.8rem; text-transform: uppercase; letter-spacing: 2px; color: var(--accent-sec); margin-bottom: 12px; font-weight: 600; }
        h2 { font-size: 2rem; font-weight: 300; margin-bottom: 24px; color: var(--text-main); }
        .feature-card {
            background: var(--surface-solid); border: 1px solid var(--border);
            border-radius: 12px; padding: 40px; box-shadow: var(--glass-shadow);
            position: relative; overflow: hidden; transition: 0.4s ease;
        }
        .feature-card::before { content: ''; position: absolute; top: 0; left: 0; width: 4px; height: 100%; background: var(--accent); }
        .feature-card.blue-card::before { background: var(--accent-sec); }
        .stack-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-top: 32px; }
        .stack-item {
            background: var(--bg); border: 1px solid var(--border); padding: 12px;
            border-radius: 6px; font-size: 0.75rem; color: var(--text-main); font-weight: 600;
        }
        .stack-item span { color: var(--accent-sec); display: block; margin-bottom: 4px; font-size: 0.65rem; text-transform: uppercase; }
        .registry-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 16px; }
        .limb-card {
            background: var(--surface-solid); border: 1px solid var(--border);
            padding: 24px; border-radius: 12px; transition: all 0.3s ease;
            position: relative; box-shadow: 0 2px 10px rgba(0,0,0,0.02);
        }
        .limb-card.active { border-color: var(--accent); }
        .limb-card:not(.active) { opacity: 0.6; }
        .limb-card:hover { transform: translateY(-4px); box-shadow: var(--glass-shadow); border-color: var(--accent-sec); opacity: 1; }
        .limb-card h3 { font-size: 1rem; margin-bottom: 8px; font-weight: 600; }
        .limb-card p { font-size: 0.8rem; color: var(--text-muted); }
        .tag { position: absolute; top: 16px; right: 16px; font-size: 0.6rem; font-weight: 600; padding: 4px 8px; border-radius: 4px; }
        .tag.active { background: rgba(5, 150, 105, 0.1); color: var(--accent); }
        .tag.pending { background: var(--bg); color: var(--text-muted); border: 1px solid var(--border); }
        .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .input-group { margin-bottom: 20px; }
        label { display: block; font-size: 0.75rem; font-weight: 600; color: var(--text-muted); margin-bottom: 8px; text-transform: uppercase; }
        input, select, textarea {
            width: 100%; padding: 14px; background: var(--bg); border: 1px solid var(--border);
            border-radius: 8px; color: var(--text-main); font-family: inherit; font-size: 0.9rem;
            transition: all 0.3s ease; outline: none;
        }
        input:focus, select:focus, textarea:focus { border-color: var(--accent); box-shadow: 0 0 0 3px rgba(5, 150, 105, 0.1); }
        .btn {
            display: inline-block; padding: 14px 32px; font-size: 0.8rem; font-weight: 600;
            text-transform: uppercase; letter-spacing: 1px; border-radius: 8px;
            cursor: pointer; transition: all 0.3s ease; text-decoration: none; text-align: center;
        }
        .btn-primary { background: var(--accent); color: #fff; border: none; box-shadow: 0 4px 15px rgba(5, 150, 105, 0.3); }
        .btn-primary:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(5, 150, 105, 0.5); }
        .btn-outline { background: transparent; color: var(--text-main); border: 1px solid var(--border); }
        .btn-outline:hover { border-color: var(--accent-sec); color: var(--accent-sec); }
        footer { text-align: center; padding: 60px 24px; border-top: 1px solid var(--border); color: var(--text-muted); font-size: 0.75rem; }
        @keyframes spin { 100% { transform: translate(-50%, -50%) translateZ(-40px) rotate(360deg); } }
        @keyframes spin-reverse { 100% { transform: translate(-50%, -50%) translateZ(15px) rotate(-360deg); } }
        @keyframes reactor-pulse { 
            0% { transform: translate(-50%, -50%) scale(0.9); opacity: 0.8; box-shadow: 0 0 20px var(--glow-core); } 
            100% { transform: translate(-50%, -50%) scale(1.3); opacity: 1; box-shadow: 0 0 60px var(--glow-outer), 0 0 100px var(--glow-core); } 
        }
        @media (max-width: 768px) {
            .mobile-menu-btn { display: block; }
            .nav-links {
                position: fixed; top: 0; right: -100%; width: 70%; height: 100vh;
                background: var(--surface-solid); 
                backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
                flex-direction: column; justify-content: center; align-items: center;
                transition: right 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94);
                border-left: 1px solid var(--border); box-shadow: -10px 0 30px rgba(0,0,0,0.1);
                z-index: 1001;
            }
            .nav-links.active { right: 0; }
            .nav-links a { font-size: 1.2rem; margin: 16px 0; }
            .mobile-menu-btn.active .bar:nth-child(1) { transform: translateY(7px) rotate(45deg); }
            .mobile-menu-btn.active .bar:nth-child(2) { opacity: 0; }
            .mobile-menu-btn.active .bar:nth-child(3) { transform: translateY(-7px) rotate(-45deg); }
            .hud-panel { display: none; }
            h1 { font-size: 2.2rem; }
            .canvas-tagline { font-size: 0.8rem; }
            .lens-wrapper { width: 250px; height: 250px; }
            .form-grid { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="grid-bg"></div>
    <nav>
        <div class="nav-container">
            <a href="#" class="logo">
                <img src="/static/app-icon.png" alt="LensDNA">
                LENS<span>DNA</span>
            </a>
            <button class="mobile-menu-btn" id="mobileMenuBtn" aria-label="Toggle Menu">
                <span class="bar"></span>
                <span class="bar"></span>
                <span class="bar"></span>
            </button>
            <div class="nav-links" id="navLinks">
                <a href="#lensdj">LensDJ Pro</a>
                <a href="#flagship">VibeMatch</a>
                <a href="#registry">Registry</a>
                <a href="#contact">Comms</a>
                <a href="/privacy.html">Privacy</a>
            </div>
        </div>
    </nav>
    <header id="hero">
        <div class="lens-wrapper" id="lensTarget">
            <div class="hud-panel hud-left mono">
                SYS.BOOT <br>
                <strong id="typewriter">INITIALIZING...</strong><br>
                Axiom Zero: <strong>ACTIVE</strong><br>
                Optic Sync: <strong style="color:var(--accent-sec)">LOCKED</strong>
            </div>
            <div class="hud-panel hud-right mono">
                TARGET LOCK<br>
                DIST: <strong id="distance">12.45</strong> m<br>
                X: <strong id="coord-x">0.00</strong> Y: <strong id="coord-y">0.00</strong><br>
                <span style="color:var(--danger)">Q1 2026 DEPLOY</span>
            </div>
            <div class="lens-container" id="lens">
                <div class="ring holo-ring-1"></div>
                <div class="ring holo-ring-2"></div>
                <div class="ring holo-ring-3"></div>
                <div class="core-app-icon">
                    <div class="quantum-core-glow"></div>
                    <img src="/static/app-icon.png" alt="LensDNA Stack">
                </div>
            </div>
        </div>
        <div class="hero-text">
            <h1>The Quantum Animism <strong>Registry</strong></h1>
            <div class="canvas-tagline mono">We turn your mobile lens into the new canvas.</div>
            <p class="hero-desc">Bridging the 100,000-year-old doctrine of Animism with modern Quantum Physics. Utilize the Sovereign Optical Stack to audit biological and material energetic signatures.</p>
            <a href="#lensdj" class="btn btn-primary">Initialize Protocol</a>
            <a href="https://x.com/lensdjing/status/2019879739599556787" target="_blank" class="btn btn-outline" style="margin-left: 10px;">Investment Dossier</a>
        </div>
    </header>
    <section id="lensdj" class="section-container">
        <div class="section-header" style="color: var(--accent-sec);">Spatial Audio Matrix</div>
        <h2>LensDNA Republic of DJs <span style="font-size: 1rem; vertical-align: middle; background: var(--accent-sec); color: #fff; padding: 4px 10px; border-radius: 4px; margin-left: 10px; font-weight: 800; text-shadow: none;">$89.99 LIFETIME</span></h2>
        
        <div class="feature-card blue-card" style="border-color: rgba(37, 99, 235, 0.3); padding: 0; overflow: hidden;">
            
            <!-- HERO IMAGE ADDED HERE -->
            <div style="width: 100%; height: 250px; background: url('/static/dj-hero.jpg') center center / cover no-repeat; border-bottom: 1px solid rgba(37, 99, 235, 0.3);">
            </div>

            <!-- TEXT CONTENT WRAPPER -->
            <div style="padding: 40px;">
                <p style="font-size: 1.1rem; color: var(--text-main); margin-bottom: 24px;">
                    <strong>Who wants to be at the top as a DJ and Producer?</strong><br><br>
                    This is <strong>agentic AI DJing</strong> powered by real-time generative AI music. The AI becomes your live co-pilot.
                </p>
                
                <div style="margin-top: 32px; padding-top: 24px; border-top: 1px solid var(--border);">
                    <p style="font-size: 0.85rem;">
                        <strong style="color: var(--accent-sec);">YOU CONTROL IT IN TWO POWERFUL WAYS:</strong><br><br>
                        • <strong>VOICE COMMANDS:</strong> Speak naturally (“drop the bass”, “build it up”, “add a vocal hook”) and the AI instantly reshapes the mix in real time.<br><br>
                        • <strong>SOVEREIGN STEM SYNTHESIS:</strong> Generate up to 240 seconds of master-quality, multi-channel electronic stems in real-time, completely bypassing traditional DAWs.
                    </p>
                </div>
                
                <div class="stack-grid mono" style="margin-top: 32px;">
                    <div class="stack-item" style="border-color: rgba(37, 99, 235, 0.3);"><span>Real-Time</span> Weighted Stem Gen</div>
                    <div class="stack-item" style="border-color: rgba(37, 99, 235, 0.3);"><span>Precise Control</span> BPM & Duration</div>
                    <div class="stack-item" style="border-color: rgba(37, 99, 235, 0.3);"><span>Performance</span> Instant Looping</div>
                    <div class="stack-item" style="border-color: rgba(37, 99, 235, 0.3);"><span>Sovereignty</span> Lifetime Ownership</div>
                </div>
                
                <div style="margin-top: 32px; padding: 24px; border: 1px solid var(--accent-sec); border-radius: 8px; background: rgba(37, 99, 235, 0.05);">
                    <h3 style="font-size: 0.9rem; text-transform: uppercase; letter-spacing: 1px; color: var(--accent-sec); margin-bottom: 12px;">
                        Perform Together
                    </h3>
                    <p style="font-size: 0.85rem; color: var(--text-main); margin-bottom: 0;">
                        You and the AI <strong>perform together</strong>, generating unprecedented audio output from the palm of your hand.<br><br>
                        <strong>No subscriptions. No plastic hardware. No limits.</strong><br><br>
                        <strong>LensDJ Pro</strong> is the only tool that lets you <strong>be</strong> the DJ and Producer at the highest level.
                    </p>
                </div>
                
                <div style="margin-top: 32px; text-align: center;">
                     <a href="/live_agent?domain=dj" class="btn btn-primary" style="background: var(--accent-sec); box-shadow: 0 4px 15px rgba(37, 99, 235, 0.3);">Launch DJ Terminal</a>
                </div>
            </div>
        </div>
    </section>
    <section id="flagship" class="section-container">
        <div class="section-header">Active Protocol</div>
        <h2>VibeMatch Sovereign</h2>
        <div class="feature-card">
            <p style="font-size: 1.1rem; color: var(--text-main); margin-bottom: 24px;">A digital instrument designed to replace subjective "gut feelings" with precise biometric and energetic data. We map the "Soul" within all natural and material things.</p>
            <div class="stack-grid mono">
                <div class="stack-item"><span>Stack 1</span> Aura Sim</div>
                <div class="stack-item"><span>Stack 2</span> Core Resonance</div>
                <div class="stack-item"><span>Stack 3</span> Expressions</div>
                <div class="stack-item"><span>Stack 4</span> Pupil Dilation</div>
            </div>
            <div style="margin-top: 32px; padding-top: 24px; border-top: 1px solid var(--border);">
                <p style="font-size: 0.85rem;">
                    <strong style="color: var(--accent);">ANIMISM AUDITING:</strong><br><br>
                    • <strong>INTERPERSONAL:</strong> Verify biological/spiritual synchronicity.<br>
                    • <strong>INTER-SPECIES:</strong> Multi-species baseline audits (Canine, Equine, Feline).<br>
                    • <strong>MATERIAL ESSENCE:</strong> Audit the spiritual essence of high-value inanimate beings (Antiques, Vehicles).
                </p>
            </div>
            <div style="margin-top: 32px; padding: 24px; border: 1px solid var(--accent); border-radius: 8px; background: rgba(5, 150, 105, 0.05);">
                <h3 style="font-size: 0.9rem; text-transform: uppercase; letter-spacing: 1px; color: var(--accent); margin-bottom: 12px;">
                    Visual Diagnostic Override
                </h3>
                <p style="font-size: 0.85rem; color: var(--text-main); margin-bottom: 12px;">
                    <strong>How to check your energetic compatibility:</strong><br>
                    Open the Neural Uplink and type either of the following commands into the terminal:
                </p>
                <ul style="list-style: none; padding-left: 0; font-family: 'Share Tech Mono', monospace; font-size: 0.8rem; color: var(--text-muted); margin-bottom: 16px;">
                    <li style="margin-bottom: 8px;">> "Run an energetic baseline scan"</li>
                    <li>> "Show me our chemistry sync"</li>
                </ul>
                <p style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 24px; border-left: 2px solid var(--accent); padding-left: 10px;">
                    <em>Note: Right-click the generated image and select "Open Image in New Tab" or "Save Image" to keep your sovereign asset.</em>
                </p>
                <div style="margin-top: 24px;">
                     <a href="/live_agent?domain=optimind" class="btn btn-primary" style="padding: 10px 20px; font-size: 0.7rem;">Launch VibeMatch</a>
                </div>
            </div>
        </div>
    </section>
    <section id="registry" class="section-container" style="padding-top: 20px;">
        <div class="section-header">Sovereign Directory</div>
        <h2>Industrial Node Registry</h2>
        <p style="margin-bottom: 32px; color: var(--text-muted);">Phase 1 (Biometrics & Essence) is active. Remaining industrial minds scheduled for rollout.</p>
        <div class="registry-grid">
            <div class="limb-card active" style="border-color: var(--accent-sec);">
                <div class="tag active mono" style="background: rgba(37, 99, 235, 0.1); color: var(--accent-sec);">ACTIVE</div>
                <h3>LensDJ Pro</h3>
                <p>Agentic AI DJing powered by Generative AI music and AR gestures.</p>
            </div>
            <div class="limb-card active">
                <div class="tag active mono">ACTIVE</div>
                <h3>VibeMatch</h3>
                <p>Quantum energetic sync & biometric compatibility auditing.</p>
            </div>
            <div class="limb-card">
                <div class="tag pending mono">Q1</div>
                <h3>ClarityDiamond</h3>
                <p>GIA-grade inclusion and refraction auditing instrument.</p>
            </div>
            <div class="limb-card">
                <div class="tag pending mono">Q1</div>
                <h3>DermaScan</h3>
                <p>Pore density & skin texture diagnostic log node.</p>
            </div>
            <div class="limb-card">
                <div class="tag pending mono">Q1</div>
                <h3>EspionageSweep</h3>
                <p>Hidden lens glint & retro-reflection detection.</p>
            </div>
            <div class="limb-card">
                <div class="tag pending mono">Q1</div>
                <h3>MarinePulse</h3>
                <p>Hull integrity & diesel fault visual detection.</p>
            </div>
            <div class="limb-card">
                <div class="tag pending mono">Q1</div>
                <h3>VintageVerify</h3>
                <p>Classic car paint oxidation & VIN authentication.</p>
            </div>
            <div class="limb-card">
                <div class="tag pending mono">Q1</div>
                <h3>AppraisalGrid</h3>
                <p>Real estate scale measurement & spatial staging.</p>
            </div>
            <div class="limb-card">
                <div class="tag pending mono">Q1</div>
                <h3>DocuLens</h3>
                <p>Legal archival: High-fidelity secure edge OCR.</p>
            </div>
        </div>
    </section>
    <section id="contact" class="section-container">
        <div class="feature-card" style="padding: 40px;">
            <div class="section-header">Publisher Node</div>
            <h2 style="margin-bottom: 24px;">Secure Transmission</h2>
            <form action="https://formspree.io/f/mreapnyb" method="POST">
                <div class="form-grid">
                    <div class="input-group">
                        <label>Identity (Authorized Personnel)</label>
                        <input type="text" name="name" required placeholder="John Doe">
                    </div>
                    <div class="input-group">
                        <label>Return Uplink (Email)</label>
                        <input type="email" name="_replyto" required placeholder="secure@signal.com">
                    </div>
                </div>
                <div class="input-group">
                    <label>Target Sub-System</label>
                    <select name="app_subject">
                        <option value="LensDJ">LensDJ Pro ($59.99 License)</option>
                        <option value="VibeMatch">VibeMatch Sovereign</option>
                        <option value="Investment">Investment Dossier Inquiry</option>
                        <option value="General">General Override</option>
                    </select>
                </div>
                <div class="input-group">
                    <label>Payload Data</label>
                    <textarea name="message" rows="4" required placeholder="Enter mission parameters..."></textarea>
                </div>
                <button type="submit" class="btn btn-primary" style="width: 100%;">Initialize Uplink</button>
            </form>
        </div>
    </section>
    <footer>
        &copy; 2026 LENSDNA.APP | QUANTUM ANIMISM STACK<br>
        ENGINEERED IN SWITZERLAND | <a href="https://x.com/lensdjing" style="color:var(--accent-sec); text-decoration:none; font-weight:600;">@lensdjing</a><br><br>
        <a href="/privacy.html#license" style="color:var(--text-muted); text-decoration:none; font-size:0.75rem; text-transform:uppercase; letter-spacing:1px; margin-bottom: 12px; display:inline-block; font-weight: 600;">View Sovereign License</a><br>
        <span class="mono" style="color: var(--danger); font-size: 0.65rem;">ZERO COOKIES. ZERO TRACKERS. TOTAL PRIVACY.</span>
    </footer>
    <script>
        const mobileMenuBtn = document.getElementById('mobileMenuBtn');
        const navLinks = document.getElementById('navLinks');
        const navItems = document.querySelectorAll('.nav-links a');
        mobileMenuBtn.addEventListener('click', () => {
            mobileMenuBtn.classList.toggle('active');
            navLinks.classList.toggle('active');
        });
        navItems.forEach(item => {
            item.addEventListener('click', () => {
                mobileMenuBtn.classList.remove('active');
                navLinks.classList.remove('active');
            });
        });
        const lens = document.getElementById('lens');
        const coordX = document.getElementById('coord-x');
        const coordY = document.getElementById('coord-y');
        const distance = document.getElementById('distance');
        function handleMove(clientX, clientY) {
            const centerX = window.innerWidth / 2;
            const centerY = window.innerHeight / 2;
            const offsetX = (clientX - centerX) / 15; 
            const offsetY = (clientY - centerY) / 15;
            lens.style.transform = `rotateX(${-offsetY}deg) rotateY(${offsetX}deg)`;
            if(coordX && coordY && distance) {
                coordX.innerText = (clientX / window.innerWidth).toFixed(3);
                coordY.innerText = (clientY / window.innerHeight).toFixed(3);
                distance.innerText = (Math.random() * (12.8 - 12.0) + 12.0).toFixed(2);
            }
        }
        document.addEventListener('mousemove', (e) => {
            handleMove(e.clientX, e.clientY);
        });
        document.addEventListener('touchmove', (e) => {
            if(e.touches.length > 0) {
                handleMove(e.touches.clientX, e.touches.clientY);
            }
        }, {passive: true});
        const logText = "Q-PROCESSORS NOMINAL.";
        const typewriterDiv = document.getElementById('typewriter');
        let charIndex = 0;
        function typeLog() {
            if (typewriterDiv && charIndex < logText.length) {
                typewriterDiv.innerHTML += logText.charAt(charIndex);
                charIndex++;
                setTimeout(typeLog, 50);
            }
        }
        if (typewriterDiv) {
            setTimeout(() => { typewriterDiv.innerHTML = ""; typeLog(); }, 1000);
        }
    </script>
</body>
</html>
"""

PRIVACY_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <link rel="icon" type="image/png" href="/static/app-icon.png">
    <title>Privacy Protocol & License | LensDNA</title>
    <link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Inter:wght@300;400;600;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #F8FAFC;
            --surface: rgba(255, 255, 255, 0.85);
            --surface-solid: #FFFFFF;
            --text-main: #0F172A;
            --text-muted: #64748B;
            --accent: #059669; 
            --accent-sec: #2563EB; 
            --border: #E2E8F0;
            --grid-color: rgba(15, 23, 42, 0.04);
            --danger: #DC2626;
            --glass-shadow: 0 8px 32px rgba(0, 0, 0, 0.05);
            --glow-core: rgba(5, 150, 105, 0.8);
            --glow-outer: rgba(37, 99, 235, 0.4);
        }
        @media (prefers-color-scheme: dark) {
            :root {
                --bg: #050505;
                --surface: rgba(17, 17, 17, 0.85);
                --surface-solid: #111111;
                --text-main: #F8FAFC;
                --text-muted: #94A3B8;
                --accent: #00FF41; 
                --accent-sec: #00E5FF; 
                --border: #222222;
                --grid-color: rgba(0, 255, 65, 0.06);
                --danger: #FF3B30;
                --glass-shadow: 0 8px 32px rgba(0, 255, 65, 0.08);
                --glow-core: #00FF41;
                --glow-outer: #00E5FF;
            }
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        html { scroll-behavior: smooth; }
        body {
            background-color: var(--bg); color: var(--text-main);
            font-family: 'Inter', system-ui, sans-serif;
            line-height: 1.6; overflow-x: hidden;
            transition: background-color 0.4s ease, color 0.4s ease;
        }
        .mono { font-family: 'Share Tech Mono', monospace; letter-spacing: 0.5px; }
        .grid-bg {
            position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
            background-image: linear-gradient(var(--grid-color) 1px, transparent 1px),
                              linear-gradient(90deg, var(--grid-color) 1px, transparent 1px);
            background-size: 40px 40px; z-index: -1; pointer-events: none;
            transition: 0.4s ease;
        }
        nav {
            position: fixed; top: 0; width: 100%; z-index: 1000;
            background: var(--surface); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--border); transition: 0.4s ease;
        }
        .nav-container {
            max-width: 1200px; margin: 0 auto; padding: 16px 24px;
            display: flex; justify-content: space-between; align-items: center;
        }
        .logo { display: flex; align-items: center; font-size: 1.1rem; font-weight: 600; color: var(--text-main); text-decoration: none; z-index: 1002; }
        .logo img { height: 28px; margin-right: 12px; border-radius: 6px; }
        .logo span { color: var(--accent); }
        .nav-links { display: flex; gap: 24px; }
        .nav-links a {
            color: var(--text-muted); text-decoration: none; font-size: 0.75rem; font-weight: 600;
            text-transform: uppercase; letter-spacing: 1px; transition: color 0.3s ease;
        }
        .nav-links a:hover { color: var(--accent); }
        .nav-links a.active { color: var(--accent); }
        .mobile-menu-btn {
            display: none; background: none; border: none; cursor: pointer; padding: 5px; z-index: 1002;
        }
        .mobile-menu-btn .bar {
            display: block; width: 24px; height: 2px; margin: 5px auto;
            background-color: var(--text-main); transition: all 0.3s ease-in-out;
        }
        header {
            min-height: 100vh; display: flex; flex-direction: column;
            justify-content: center; align-items: center; position: relative;
            padding: 120px 20px 40px 20px; overflow: hidden;
        }
        .lens-wrapper {
            position: relative; width: 320px; height: 320px;
            perspective: 1200px; margin-bottom: 50px;
        }
        .lens-container {
            width: 100%; height: 100%; position: absolute;
            transform-style: preserve-3d; 
            transition: transform 0.1s cubic-bezier(0.25, 0.46, 0.45, 0.94);
        }
        .ring { 
            position: absolute; border-radius: 50%; top: 50%; left: 50%;
            pointer-events: none; transform-style: preserve-3d;
        }
        .holo-ring-1 { 
            width: 140%; height: 140%; 
            border: 2px dashed var(--accent-sec); opacity: 0.4; 
            animation: spin 25s linear infinite; 
            transform: translate(-50%, -50%) translateZ(-40px);
            box-shadow: inset 0 0 20px rgba(37, 99, 235, 0.2);
        }
        .holo-ring-2 { 
            width: 110%; height: 110%; 
            border: 4px solid transparent; 
            border-top-color: var(--accent); border-bottom-color: var(--accent); 
            animation: spin-reverse 12s linear infinite; 
            transform: translate(-50%, -50%) translateZ(15px); 
            box-shadow: 0 0 30px rgba(0, 255, 65, 0.1);
            filter: drop-shadow(0 0 8px var(--accent));
        }
        .holo-ring-3 { 
            width: 85%; height: 85%; 
            border: 1px dotted var(--text-main); opacity: 0.6; 
            animation: spin 8s linear infinite; 
            transform: translate(-50%, -50%) translateZ(60px); 
        }
        .core-app-icon {
            position: absolute; width: 70%; height: 70%; 
            top: 50%; left: 50%; 
            transform: translate(-50%, -50%) translateZ(35px); 
            transform-style: preserve-3d; 
            display: flex; justify-content: center; align-items: center;
        }
        .core-app-icon img {
            width: 100%; height: 100%; position: relative; z-index: 10;
            filter: drop-shadow(0 20px 30px rgba(0,0,0,0.5)) drop-shadow(0 0 15px var(--accent));
        }
        .quantum-core-glow {
            position: absolute; width: 45%; height: 45%; 
            top: 50%; left: 50%; transform: translate(-50%, -50%); 
            background: radial-gradient(circle, var(--glow-core) 0%, var(--glow-outer) 60%, transparent 80%); 
            border-radius: 50%; filter: blur(12px); z-index: 5; 
            animation: reactor-pulse 2s infinite alternate cubic-bezier(0.4, 0, 0.2, 1);
        }
        .hud-panel {
            position: absolute; background: var(--surface); backdrop-filter: blur(8px);
            border: 1px solid var(--border); padding: 12px 16px; border-radius: 8px;
            font-size: 0.7rem; color: var(--text-muted); box-shadow: var(--glass-shadow);
            pointer-events: none; transition: 0.4s ease; z-index: 20;
        }
        .hud-left { top: 0%; left: -65%; text-align: left; border-left: 3px solid var(--accent); }
        .hud-right { bottom: 0%; right: -65%; text-align: right; border-right: 3px solid var(--accent-sec); }
        .hud-panel strong { color: var(--accent); }
        .hero-text { text-align: center; max-width: 700px; z-index: 10; position: relative; }
        h1 { font-size: 2.8rem; font-weight: 300; letter-spacing: -1px; margin-bottom: 8px; color: var(--text-main); }
        h1 strong { font-weight: 800; color: var(--accent); }
        .canvas-tagline {
            font-size: 1.1rem; font-weight: 600; color: var(--accent);
            text-transform: uppercase; letter-spacing: 2px;
            margin-bottom: 24px; text-shadow: 0 0 15px rgba(0, 255, 65, 0.3);
            display: inline-block; padding: 8px 16px;
            border: 1px solid rgba(0, 255, 65, 0.2); border-radius: 4px;
            background: rgba(0, 255, 65, 0.05);
        }
        .hero-desc { font-size: 1.05rem; color: var(--text-muted); margin-bottom: 32px; }
        .section-container { max-width: 1000px; margin: 0 auto; padding: 80px 24px; }
        .section-header { font-size: 0.8rem; text-transform: uppercase; letter-spacing: 2px; color: var(--accent-sec); margin-bottom: 12px; font-weight: 600; }
        .feature-card {
            background: var(--surface-solid); border: 1px solid var(--border);
            border-radius: 12px; padding: 60px; box-shadow: var(--glass-shadow);
            position: relative; overflow: hidden; transition: 0.4s ease;
        }
        .feature-card::before { content: ''; position: absolute; top: 0; left: 0; width: 4px; height: 100%; background: var(--accent); }
        .btn {
            display: inline-block; padding: 14px 32px; font-size: 0.8rem; font-weight: 600;
            text-transform: uppercase; letter-spacing: 1px; border-radius: 8px;
            cursor: pointer; transition: all 0.3s ease; text-decoration: none; text-align: center;
        }
        .btn-primary { background: var(--accent); color: #fff; border: none; box-shadow: 0 4px 15px rgba(5, 150, 105, 0.3); }
        .btn-primary:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(5, 150, 105, 0.5); }
        .btn-outline { background: transparent; color: var(--text-main); border: 1px solid var(--border); }
        .btn-outline:hover { border-color: var(--accent-sec); color: var(--accent-sec); }
        footer { text-align: center; padding: 60px 24px; border-top: 1px solid var(--border); color: var(--text-muted); font-size: 0.75rem; }
        @keyframes spin { 100% { transform: translate(-50%, -50%) translateZ(-40px) rotate(360deg); } }
        @keyframes spin-reverse { 100% { transform: translate(-50%, -50%) translateZ(15px) rotate(-360deg); } }
        @keyframes reactor-pulse { 
            0% { transform: translate(-50%, -50%) scale(0.9); opacity: 0.8; box-shadow: 0 0 20px var(--glow-core); } 
            100% { transform: translate(-50%, -50%) scale(1.3); opacity: 1; box-shadow: 0 0 60px var(--glow-outer), 0 0 100px var(--glow-core); } 
        }
        .feature-card h2 { font-size: 1.4rem; font-weight: 600; color: var(--text-main); margin-top: 40px; margin-bottom: 16px; border-bottom: 1px solid var(--border); padding-bottom: 8px; }
        .feature-card h2:first-of-type { margin-top: 0; }
        .feature-card p, .feature-card li { font-size: 0.95rem; color: var(--text-muted); margin-bottom: 16px; line-height: 1.7; }
        .feature-card ul { margin-left: 20px; margin-bottom: 24px; }
        .feature-card strong { color: var(--text-main); font-weight: 600; }
        .feature-card a { color: var(--accent-sec); text-decoration: none; font-weight: 600; }
        .feature-card a:hover { text-decoration: underline; }
        .legal-box { background: var(--bg); padding: 20px; border-radius: 8px; border: 1px solid var(--border); border-left: 4px solid var(--accent); margin: 24px 0; }
        .disclaimer-box { background: rgba(220, 38, 38, 0.05); padding: 20px; border-radius: 8px; border: 1px solid rgba(220, 38, 38, 0.2); border-left: 4px solid var(--danger); margin: 24px 0; font-size: 0.85rem; color: var(--text-muted); }
        .audit-tag { display: inline-block; font-size: 0.7rem; padding: 4px 8px; background: rgba(220, 38, 38, 0.1); color: var(--danger); border-radius: 4px; margin-bottom: 32px; }
        @media (max-width: 768px) {
            .mobile-menu-btn { display: block; }
            .nav-links {
                position: fixed; top: 0; right: -100%; width: 70%; height: 100vh;
                background: var(--surface-solid); 
                backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
                flex-direction: column; justify-content: center; align-items: center;
                transition: right 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94);
                border-left: 1px solid var(--border); box-shadow: -10px 0 30px rgba(0,0,0,0.1);
                z-index: 1001;
            }
            .nav-links.active { right: 0; }
            .nav-links a { font-size: 1.2rem; margin: 16px 0; }
            .mobile-menu-btn.active .bar:nth-child(1) { transform: translateY(7px) rotate(45deg); }
            .mobile-menu-btn.active .bar:nth-child(2) { opacity: 0; }
            .mobile-menu-btn.active .bar:nth-child(3) { transform: translateY(-7px) rotate(-45deg); }
            .hud-panel { display: none; }
            h1 { font-size: 2.2rem; }
            .canvas-tagline { font-size: 0.8rem; }
            .lens-wrapper { width: 250px; height: 250px; }
            .feature-card { padding: 30px 20px; }
        }
    </style>
</head>
<body>
    <div class="grid-bg"></div>
    <nav>
        <div class="nav-container">
            <a href="/" class="logo">
                <img src="/static/app-icon.png" alt="LensDNA">
                LENS<span>DNA</span>
            </a>
            <button class="mobile-menu-btn" id="mobileMenuBtn" aria-label="Toggle Menu">
                <span class="bar"></span>
                <span class="bar"></span>
                <span class="bar"></span>
            </button>
            <div class="nav-links" id="navLinks">
                <a href="/#flagship">VibeMatch</a>
                <a href="/#registry">Registry</a>
                <a href="/#contact">Comms</a>
                <a href="/privacy.html" class="active">Privacy</a>
            </div>
        </div>
    </nav>
    <header id="hero">
        <div class="lens-wrapper" id="lensTarget">
            <div class="hud-panel hud-left mono">
                SYS.BOOT <br>
                <strong id="typewriter">INITIALIZING...</strong><br>
                Audit Log: <strong>ACTIVE</strong><br>
                Encryption: <strong style="color:var(--accent-sec)">TLS 1.3</strong>
            </div>
            <div class="hud-panel hud-right mono">
                DATA STATE<br>
                RAM: <strong id="distance">EPHEMERAL</strong><br>
                STORED: <strong id="coord-x">0.00</strong> KB<br>
                <span style="color:var(--danger)">NO COOKIES</span>
            </div>
            <div class="lens-container" id="lens">
                <div class="ring holo-ring-1"></div>
                <div class="ring holo-ring-2"></div>
                <div class="ring holo-ring-3"></div>
                <div class="core-app-icon">
                    <div class="quantum-core-glow"></div>
                    <img src="/static/app-icon.png" alt="LensDNA Stack">
                </div>
            </div>
        </div>
        <div class="hero-text">
            <h1>Data Sovereignty <strong>Protocol</strong></h1>
            <div class="canvas-tagline mono">Zero Cookies. Total Privacy.</div>
            <p class="hero-desc">LensDNA operates under strict adherence to the Swiss Federal Act on Data Protection (FADP) and the General Data Protection Regulation (GDPR).</p>
            <a href="#policy" class="btn btn-primary">Read Protocol</a>
            <a href="/" class="btn btn-outline" style="margin-left: 10px;">Return to Hub</a>
        </div>
    </header>
    <section id="policy" class="section-container">
        <div class="feature-card">
            <div class="audit-tag mono">LAST SECURITY AUDIT: FEBRUARY 2026</div>
            <h2>1. Data Collection & Telemetry</h2>
            <p>We process data in two distinct isolation chambers: <strong>Voluntary Input</strong> and <strong>Ephemeral Telemetry</strong>.</p>
            <ul>
                <li><strong>Voluntary Input:</strong> Identity, Comm Channels, and Payload data entered via the Publisher Node.</li>
                <li><strong>Ephemeral Visual Telemetry:</strong> To perform VibeMatch and Registry audits, visual data is processed entirely in <em>Ephemeral RAM</em>. Once the energetic baseline analysis is complete, the raw data is completely purged from the active cache. <strong>We do not maintain databases of biological faces or location scans.</strong></li>
            </ul>
            <h2>2. Third-Party Neural Links</h2>
            <p>LensDNA acts as a secure sovereign wrapper. For industrial-grade logic, localized data tokens are securely tunneled to external matrices:</p>
            <div class="legal-box">
                <strong>x.ai (Grok 4.1):</strong> Deployed for logic synthesis and energetic interpretation.<br>
                <a href="https://x.ai/legal/privacy-policy" target="_blank">View x.ai Protocol</a>
            </div>
            <div class="legal-box">
                <strong>Google (Gemini 3):</strong> Deployed for advanced optical character recognition (OCR) and raster alignment.<br>
                <a href="https://policies.google.com/privacy" target="_blank">View Google Protocol</a>
            </div>
            <h2>3. Biometric Privacy Architecture</h2>
            <p>LensDNA analyzes transient data (e.g., Micro-Expressions, Pupil Dilation). This data exists as temporary mathematical vectors and is NEVER formulated into identifiable biometric profiles.</p>
            <ul>
                <li><strong>Retention:</strong> 0 Days (Immediate Purge post-calculation).</li>
                <li><strong>Storage:</strong> Null.</li>
                <li><strong>Monetization:</strong> Zero corporate data brokering.</li>
            </ul>
            <h2>4. Zero-Cookie Architecture</h2>
            <p>We deploy ZERO persistent tracking cookies, pixels, or cross-site fingerprinting nodes. Your session is confined strictly to the active DOM window.</p>
            <h2>5. Jurisdiction Node</h2>
            <p>This protocol is governed by the laws of <strong>Bern, Switzerland</strong>.</p>
            <p>
                <strong>Data Controller:</strong><br>
                Jolanda Christina Maria Wevers<br>
                Utzigen, Switzerland<br>
                <a href="/#contact">SECURE COMMS</a>
            </p>
            <h2 id="license">6. Sovereign Infrastructure License</h2>
            <div class="legal-box mono" style="font-size: 0.8rem; white-space: pre-wrap; line-height: 1.6; border-left-color: var(--accent-sec);">LENSDNA SOVEREIGN INFRASTRUCTURE LICENSE
Version 1.0 (Non-Commercial Source-Available)

This license governs use of the accompanying software, including the Sovereign Optic Stack and associated Industrial Node Registry.

1. PERMISSIONS
You are permitted to view, download, and execute this source code for personal, non-commercial, and evaluation purposes only.

2. RESTRICTIONS
- NO COMMERCIAL USE: You may not use this software or its architectural patterns (Quantum Animism Registry, VibeMatch Protocol) for any commercial purpose or financial gain.
- NO DERIVATIVES: You may not distribute modified versions of the LensDNA Optic Stack.
- TRADE SECRET PROTECTION: The specific modulation parameters for "Aura Sim", "Core Resonance", and the Ephemeral Telemetry processing logic are declared as Trade Secrets of the author and are withheld from this public disclosure.

3. ATTRIBUTION
Any authorized academic or research reference to this architecture must credit: "LensDNA Sovereign Optic Stack by Jolanda Christina Maria Wevers (@lensdjing)".

4. TERMINATION
This license terminates automatically if you breach any of its terms.

Licensed under the PolyForm Non-Commercial License 1.0.0.
For commercial licensing, initiate transmission via the Publisher Node.</div>
            <h2>7. Legal Disclaimer</h2>
            <div class="disclaimer-box">
                <strong>LEGAL DISCLAIMER (LENSDNA)</strong><br><br>
                LensDNA utilizes "Quantum Animism Models" and biometric methodologies trained on public frameworks and academic papers. References to specific industries, roles, corporate entities, or trademarks (e.g., "VibeMatch Sovereign", "ClarityDiamond", "MarinePulse") are for simulation, energetic modeling, and illustrative purposes only.<br><br>
                This output is generated by Artificial Intelligence and optical processing based solely on the user's environmental input or prompt. Artificial Intelligence and computer vision can produce errors, hallucinations, inaccuracies, or incomplete information. This software is not affiliated with, endorsed by, sponsored by, or representative of any referenced entity, person, or organization.<br><br>
                LensDNA accepts no liability whatsoever for any reliance on, use of, or consequences arising from the outputs. Users are solely responsible for independently verifying, double-checking, and validating all outputs before any operational, financial, medical, legal, professional, or other use.<br><br>
                <strong>Jurisdiction:</strong> Bern, Switzerland. <br>
                &copy; 2026 LensDNA.app / Jolanda Christina Maria Wevers. All rights reserved.
            </div>
        </div>
    </section>
    <footer>
        &copy; 2026 LENSDNA.APP | QUANTUM ANIMISM STACK<br>
        ENGINEERED IN SWITZERLAND | <a href="https://x.com/lensdjing" style="color:var(--accent-sec); text-decoration:none; font-weight:600;">@lensdjing</a><br><br>
        <span class="mono" style="color: var(--danger); font-size: 0.65rem;">ZERO COOKIES. ZERO TRACKERS. TOTAL PRIVACY.</span>
    </footer>
    <script>
        const mobileMenuBtn = document.getElementById('mobileMenuBtn');
        const navLinks = document.getElementById('navLinks');
        const navItems = document.querySelectorAll('.nav-links a');
        mobileMenuBtn.addEventListener('click', () => {
            mobileMenuBtn.classList.toggle('active');
            navLinks.classList.toggle('active');
        });
        navItems.forEach(item => {
            item.addEventListener('click', () => {
                mobileMenuBtn.classList.remove('active');
                navLinks.classList.remove('active');
            });
        });
        const lens = document.getElementById('lens');
        function handleMove(clientX, clientY) {
            const centerX = window.innerWidth / 2;
            const centerY = window.innerHeight / 2;
            const offsetX = (clientX - centerX) / 15; 
            const offsetY = (clientY - centerY) / 15;
            lens.style.transform = `rotateX(${-offsetY}deg) rotateY(${offsetX}deg)`;
        }
        document.addEventListener('mousemove', (e) => {
            handleMove(e.clientX, e.clientY);
        });
        document.addEventListener('touchmove', (e) => {
            if(e.touches.length > 0) {
                handleMove(e.touches.clientX, e.touches.clientY);
            }
        }, {passive: true});
        const logText = "PRIVACY ENFORCED.";
        const typewriterDiv = document.getElementById('typewriter');
        let charIndex = 0;
        function typeLog() {
            if (typewriterDiv && charIndex < logText.length) {
                typewriterDiv.innerHTML += logText.charAt(charIndex);
                charIndex++;
                setTimeout(typeLog, 50);
            }
        }
        if (typewriterDiv) {
            setTimeout(() => { typewriterDiv.innerHTML = ""; typeLog(); }, 1000);
        }
    </script>
</body>
</html>
"""