import os
import requests
import json
import base64

def synthesize_text_gcp(text: str, api_key: str, language_code: str = "en") -> bytes or None:
    """
    Synthesizes text to speech using Google Cloud Text-to-Speech REST API.
    Uses the provided Gemini API key for authentication.
    """
    if not api_key or not text.strip():
        return None
        
    url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={api_key}"
    headers = {"Content-Type": "application/json"}
    
    # Map language parameter to target GCP voice configuration
    lang_map = {
        "en": ("en-US", "en-US-Neural2-F"),
        "hi": ("hi-IN", "hi-IN-Neural2-F"),
        "es": ("es-ES", "es-ES-Neural2-F")
    }
    lang_code, voice_name = lang_map.get(language_code, ("en-US", "en-US-Neural2-F"))
    
    # Configure request payload with Neural2 voice for high quality
    data = {
        "input": {
            "text": text
        },
        "voice": {
            "languageCode": lang_code,
            "name": voice_name
        },
        "audioConfig": {
            "audioEncoding": "MP3"
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        if response.status_code == 200:
            res_json = response.json()
            audio_content_b64 = res_json.get("audioContent")
            if audio_content_b64:
                return base64.b64decode(audio_content_b64)
        else:
            print(f"GCP TTS REST failed with status {response.status_code}: {response.text}")
    except Exception as e:
        print(f"Error calling GCP TTS REST: {e}")
        
    return None

def transcribe_audio_gcp(audio_bytes: bytes, api_key: str, language_code: str = "en") -> str or None:
    """
    Transcribes audio bytes to text using Google Cloud Speech-to-Text REST API.
    Uses the provided Gemini API key for authentication.
    """
    if not api_key or not audio_bytes:
        return None
        
    url = f"https://speech.googleapis.com/v1/speech:recognize?key={api_key}"
    headers = {"Content-Type": "application/json"}
    
    # Encode audio bytes to base64
    audio_content_b64 = base64.b64encode(audio_bytes).decode("utf-8")
    
    # Map input language to STT locale and alternative lang codes
    lang_map = {
        "en": ("en-IN", ["hi-IN", "en-US"]),
        "hi": ("hi-IN", ["en-IN", "en-US"]),
        "es": ("es-ES", ["es-US", "en-US"])
    }
    primary_lang, alternatives = lang_map.get(language_code, ("en-IN", ["hi-IN", "en-US"]))
    
    # Configure payload with auto-detection configurations
    data = {
        "config": {
            "encoding": "ENCODING_UNSPECIFIED",
            "languageCode": primary_lang,
            "alternativeLanguageCodes": alternatives,
            "enableAutomaticPunctuation": True
        },
        "audio": {
            "content": audio_content_b64
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=15)
        if response.status_code == 200:
            res_json = response.json()
            results = res_json.get("results", [])
            if results:
                transcript = results[0].get("alternatives", [{}])[0].get("transcript")
                return transcript
        else:
            print(f"GCP STT REST failed with status {response.status_code}: {response.text}")
    except Exception as e:
        print(f"Error calling GCP STT REST: {e}")
        
    return None
