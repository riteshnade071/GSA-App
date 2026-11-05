# Awaaz ka permanent fix (sunna)

## Pehle kya galat tha
Phone ka Google SpeechRecognizer (hi-IN) mixed Hindi-English aur door se bolne par galat sunta tha, aur mic kabhi
Vosk ka, kabhi recognizer ka hota tha (beech me gap).

## Ab kya hota hai
```
Mic (ek hi, 16 kHz)
  ├─ Dsp: shor kam + door ki awaaz tez (40x tak) + clipping nahi
  ├─ WAKE : "हे साकुरा" / "साकुरा" phone par hi (Hindi Vosk, offline)
  └─ CAPTURE: wake ke baad ek hukm record (bolna shuru hone se 0.3 s pehle se)
        └─► page ──► /api/stt ──► Groq Whisper-large-v3 (ya Gemini audio) ──► text ──► Sakura
```
- App ke naam (WhatsApp, YouTube, ...) aur hukm ke shabd STT ko pehle se bataye jaate hain, isliye "व्हाट्सएप", "reels", "scroll" sahi pakde jaate hain.
- Shor / khaamoshi / "thanks for watching" jaisi bakwaas Whisper ki galti filter hoti hai.
- Server STT fail ho to phone ka recognizer Hindi (hi-IN) me fallback karta hai. Voice commands English ya Roman Hinglish me transcribe nahi kiye jaate.

## Render par karna
1. Groq (console.groq.com) par free API key banao, Render > Environment me `GROQ_API_KEY` daalo. (Na daalo to Gemini se chalega, thoda dheema.)
2. Deploy. `/api/config` me `"stt":"groq"` (ya `"gemini"`) dikhna chahiye.

## Door se sunna: sachchai
- Software 20-40 guna tak awaaz badhata hai, par mic ki bhautik seema hai. Shaant kamre me ~2-3 m tak theek, TV/pankhe ke saath ~1 m.
- Phone ko khade rakho, mic ka chhed (neeche) dhaka na ho, cover/haath na ho.
- Bahut dheemi awaaz par status line me likha aata hai: "Awaaz bahut dheemi thi, thoda paas aake bolo".

## Privacy
- "हे साकुरा" ka sunna phone par hi hota hai, kahin nahi jaata.
- Sirf wake ke BAAD ka ek hukm (max 12 s) STT server ko jaata hai, aur kahin save nahi hota.

## Dhyan se tune karne ki jagah
- `Dsp.kt`: `speech = rms > max(noise * 2f, 55f)` (kam karo = aur dheemi awaaz pakdegi, par shor se jhootha trigger badhega).
- `Mic.kt`: `endSilence` 40 = 0.8 s chup par record khatam.
- `stt_engine.py`: `BASE_VOCAB` me apne aam shabd jodo.

## Hindi wake-word setup
- Wake phrase: **"हे साकुरा"** or **"साकुरा"**.
- Vosk ka Hindi small model pehli baar internet se lagbhag 42 MB download hota hai; uske baad wake detection phone par offline hota hai.
- Agar naam aapke accent me galat sunai de, Phone setup me **Wake sikhao** ka use karke 5 baar "साकुरा" bolkar rukna. Learned ASR phrase ko wake matcher me allow kiya jayega.
- Wake test ON karke status line me "Wake sun raha" ke baad jo Hindi text dikhe, wahi troubleshooting ke liye bhejein.

## Hindi-only wake and commands (2026-11-03)
- Wake phrase: "हे साकुरा" or "साकुरा".
- On-device wake model: Vosk small Hindi (downloaded once, about 42 MB).
- Command transcription is fixed to Hindi (hi-IN / hi); Hindi words are expected in Devanagari.
- English brand names and market tickers may remain in their official spelling.
- The older English Porcupine wake path is opt-in only.
