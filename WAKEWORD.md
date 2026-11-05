# Hindi wake word setup (offline)

1. App ko pehli baar start karte waqt internet ON rakhein.
2. Sakura Vosk ka official small Hindi model (`vosk-model-small-hi-0.22`, ~42 MB) download karegi.
3. Model app ke private storage me rahega; wake-word audio phone par hi process hota hai.
4. Wake phrase bolein: **"हे साकुरा"** ya **"साकुरा"**.
5. Agar aapke accent me detect na ho, Phone setup > **Wake sikhao** me jaakar 5 baar "साकुरा" bolein, har baar 1-2 second rukhein.
6. Wake test ON karke status line me recognized Hindi text dekhein.

Hindi command recognition bhi `hi-IN` par fixed hai. English command phrases aur Roman Hinglish commands supported nahi hain. App/brand names aur market tickers jaise TradingView, WhatsApp, XAUUSD apni official spelling me reh sakte hain.

Model source: https://alphacephei.com/vosk/models/vosk-model-small-hi-0.22.zip
License: Apache 2.0. Model details: https://alphacephei.com/vosk/models
