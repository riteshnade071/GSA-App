# Sakura Android app (GitHub se build hota hai, Android Studio nahi chahiye)

1. GitHub par naya private repo banao (jaise sakura-app) aur is folder ki SAARI files upload karo
   (hidden folder .github samet). 
2. Repo me Actions tab -> "Build APK" -> Run workflow.
3. 5-10 minute baad run khulega -> neeche Artifacts -> sakura-apk download karo -> zip kholo -> app-debug.apk
4. APK ko phone me bhejo aur install karo (Unknown sources allow karna padega).
5. App pehli baar server ka address maangegi: apna Render ka https link.

## Overlay mode (screen par aana)
App me Phone setup -> "Dusri apps ke upar dikhne ki permission" ON karo, phir "Screen par aao".
Notification me "Band karo" se rok sakte ho.

## Haath (screen control) - naya
1. Naya APK install karo. Phone setup -> "Haath / screen control (Accessibility) ON karo" -> Sakura haath -> ON.
   Android 13+ par agar ON nahi hota (grey hai): Settings -> Apps -> Sakura -> teen dot (menu) -> "Allow restricted settings", phir dobara ON karo.
2. Server (Umiko repo) me main.py naya wala lagao (usme naye tools pehle se register hain).
3. Bolo: "YouTube kholo aur lofi search karo", "dheere dheere neeche scroll karo", "pehle video pe click karo".
   Do haath screen par dikhte hain; Send/pay/delete jaise button se pehle tumse poochhti hai.
4. Rokne ke liye: notification me "Band karo", ya bolo "ruk jao" (stop_agent).

## Chhoti girl
Dusri app khulte hi girl chhoti (khadi, pendrive jitni) ho jaati hai. Size badalna ho to OverlayService.kt me MINI_W_DP / MINI_H_DP badlo.
Use ungli se kahin bhi khiska sakte ho (jab haath kaam na kar rahe ho).

## Wake word bina Picovoice ke (naya)
Ab "Hey Sakura" ke liye Picovoice/account/company email nahi chahiye. App Vosk (free, offline) use karti hai.
- Pehli baar internet par ek chhota model (~40 MB) apne aap utarti hai, phir sab offline.
- Picovoice key pehle se daali ho to wahi chalegi; key na ho to Vosk.
- Agar wo "Sakura" sahi na pakde: Phone setup -> "Wake test ON" karo. Jo sunai dega wo screen par likha aayega.
  Wo mujhe bhejo, main shabdon ki list theek kar dunga.

## Hamesha ON rehna
1. Phone setup -> "Battery optimization hatao" -> Sakura -> Allow. (Ye zaroori hai, warna phone mic band kar deta hai.)
2. App kholo, mic ON karo, phir bahar nikal jao ya screen band kar do. Sakura notification ke saath background me sunti rahegi.
3. "Hey Sakura" bolo -> jaagegi. Band karne ke liye bolo "so jao" ya "close" (akela). Tab tak chalti rahegi.
4. Phone restart ke baad app ek baar kholna padega (Android 14 boot par mic service chalne nahi deta).
5. Background me sunna band rakhna ho: Phone setup -> "Background me hamesha sunna" OFF.
Dhyan: hamesha sunne se battery thodi zyada lagti hai.

## Chhoti girl (4 cm)
Ab asli 4 cm lambi aur 1.8 cm chaudi. Use ungli se kahin bhi khiskao. Sirf utni jagah dabti hai, baaki screen par tap normal chalta hai.
Kaam karte waqt (haath dikhte waqt) wo touch se hat jaati hai taaki tap uske neeche na atke.

## v4 (naya)
- **Pehli baar** ye APK install karne se pehle purani Sakura app uninstall karo (signing key ab fixed hai). Uske baad har naya APK seedha update hoga, permissions reset nahi hongi.
- Install ke baad app kholo: 3 second me "Sakura status" dikhega (kya-kya ON hai). Phone setup > "Status check" se kabhi bhi dekho. Jo ❌ ho use "Pehla theek karo" se theek karo.
- Sabse zaroori: **Overlay permission** (iske bina Sakura screen par nahi aati, sirf haath dikhte hain) aur **Accessibility**.
- Wake word: pehli baar Indian English model (~40 MB) utarta hai. Page ki status line me "Wake sun raha: ..." dikhta hai ki wo kya sun rahi hai.
- App ka naam Hindi/galat bol do to bhi awaaz se milti app dhoondh leti hai. Na mile to sabse milti apps ke naam LLM ko dikhte hain.
- Kaam fail ho to screen par ⚠ ke saath wajah dikhti hai.

## Trading chart ka analysis (naya)
1. TradingView ya apni trading app kholo, chart saaf screen par rakho.
2. Bolo: "Hey Sakura, analysis karo" ya sirf "analyze" / "analysis" / "deep analysis". Current chart screen active ho to ye sab full deep investigation chalate hain (multi-timeframe + historical views + public research/news + bullish/bearish scenarios).
3. Sakura (overlay me) ek screenshot leti hai, server ke vision AI ko bhejti hai, aur trend, levels, indicators aur do scenarios samjha deti hai. Har baar bolne par naya chart padhti hai ("live" matlab jab bolo tab abhi ki screen).
- Pehli baar: Accessibility ek baar OFF karke dobara ON karo (screenshot ki ijazat naye version me judi hai). Android 11+ chahiye.
- Server par GEMINI_API_KEY ya ANTHROPIC_API_KEY chahiye (vision).
- Screenshot sirf bolne par, sirf analysis ke liye, ek baar bheja jata hai. Bank/password/OTP wali screen par wo mana kar deti hai.
- Ye sirf chart padhna hai, financial salah nahi. Stop-loss aur risk apna khud tay karo.

## Photo Studio (free manual handoff)

See `SAKURA_PHOTO_STUDIO.md`. Sakura shares the source photo and edit prompt to an installed AI app only after confirmation; you manually press Send, save the generated result, then use `import edited photo` to save it in Gallery / Pictures/Sakura. `compare photos` opens an offline before/after viewer. No paid image API is included.

## Futuristic Sakura dashboard
The Android app displays the hosted Sakura web interface inside its WebView. The v11 hosted frontend adds a responsive neon command-center layout around the existing live VRM avatar and keeps the Android bridge, voice controls, photo handoff, memory, and market tools connected. Update the hosted `Umiko-main` frontend as well as installing the Android project; the visual dashboard is served by the backend website, not compiled as a static Android wallpaper.
