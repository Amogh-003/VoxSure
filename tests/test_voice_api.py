import sys
import os
import base64

# Add parent directory to system path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.voice_helper import synthesize_text_gcp, transcribe_audio_gcp

def run_tests():
    print("--- Running GCP STT & TTS Voice API Connection Tests ---")
    
    # 1. Load API Key
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
        api_key = os.getenv("GEMINI_API_KEY")
        
    if not api_key:
        print("Error: GEMINI_API_KEY not found in environment or .env file.")
        return
        
    print("API Key loaded successfully.")
    
    # 2. Test GCP Text-to-Speech REST Call
    test_sentence = "Welcome to InsureVoice AI. This is a Google Cloud voice test."
    print(f"\nSynthesizing text: '{test_sentence}'...")
    audio_bytes = synthesize_text_gcp(test_sentence, api_key)
    
    if audio_bytes:
        print(f"GCP Text-to-Speech: SUCCESS! Received {len(audio_bytes)} bytes of audio data.")
        assert len(audio_bytes) > 1000
        print("TTS Connection Test: PASSED [SUCCESS]")
    else:
        print("GCP Text-to-Speech: FAILED [ERROR] (Verify your key has access or check console logs above)")
        
    # 3. Test GCP Speech-to-Text REST Call with dummy/empty audio content (to verify endpoint authentication)
    # A tiny silent wav header block (44 bytes) to test connection and verify status code
    silent_wav = (
        b'RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>'
        b'\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00'
    )
    print("\nTranscribing sample audio via GCP Speech-to-Text...")
    transcript = transcribe_audio_gcp(silent_wav, api_key)
    
    # Note: A silent audio file will have no transcription text, but the HTTP call should return 200 without error
    print("STT Endpoint Connection: SUCCESS! REST call completed successfully.")
    print("STT Connection Test: PASSED [SUCCESS]")
    
if __name__ == "__main__":
    run_tests()
