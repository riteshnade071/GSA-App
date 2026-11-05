# Sakura ka seekhna aur yaad rakhna

Sakura ka dimaag ab 4 tarah ki yaad rakhta hai (page me 🧠 button se dekho, hatao, backup lo):

| Yaad | Kya hai | Kahan kaam aati hai |
|---|---|---|
| 📝 yaad (fact) | Master ke baare me baatein | Har jawab me kaam ki 8 baatein dimaag ko di jaati hain |
| 📘 seekh (lesson) | galti se seekha niyam ("reels = Instagram Reels") | Prompt me `SEEKHA:` ke naam se, jab baat usse milti ho |
| 🔁 matlab (alias) | kya suna -> kya matlab ("insta = Instagram") | Hukm AI ko jaane se PEHLE theek ho jaata hai |
| ⚡ recipe | jo kaam sahi hua uske steps | Agli baar bina AI ke, turant, tez chalti hai |

## Kaise seekhti hai
1. **Galti pakadne par:** kaam ke baad 2 minute ke andar Master "nahi", "galat", "maine X bola tha" bole to: galat recipe hat jaati hai, aur server (`/api/learn`) Master ke shabdon se 1-2 chhote niyam/matlab banata hai.
2. **Apni galti se:** agar "insta" nahi mila aur AI ne "Instagram" se khol diya, to "insta = Instagram" apne aap seekh leti hai. Galat koshishein recipe me nahi aati, sirf sahi raasta aata hai.
3. **Sikhane par:** "yaad rakho ki..." / "aage se aisa karna" / "ye bhool jao".
4. **Jo kaam bar-bar sahi hota hai:** recipe ban jaati hai. "YouTube pe lofi search karo" ke baad "YouTube pe jazz search karo" bhi turant chalta hai (query badalti hai, raasta wahi).

## Tez aur sahi kaise
- Recipe me AI ke 3-4 round-trip nahi lagte, haath bhi tez chalte hain (`fast`).
- Har step ke baad dekhti hai ki screen badli ya nahi. Button na mile to 4 baar ruk-kar koshish. Phir bhi na ho to recipe chhodkar AI se naye sire se karti hai, aur recipe ko "galat" ginti hai. 2 baar galat > sahi to recipe hat jaati hai.
- Master ne galat kaha to turant recipe hat jaati hai.

## Suraksha (ye kabhi nahi badalta)
- Password / OTP / PIN / card / Aadhaar / PAN / 6+ ank kabhi yaad nahi hote, client aur server dono jagah filter.
- Seekhe hue niyam safety nahi badal sakte: send/pay/delete se pehle haan poochna, bank/password screen par kaam na karna.
- Recipe me sirf surakshit tool (open_app, tap, type_text, scroll, ...). `send`, `dial`, `pay`, `delete` jaise button wali recipe kabhi nahi banti.
- Seekhne ke liye sirf Master ke shabd server ko jaate hain, screen ka text nahi.
- 🧠 panel me "Seekhna: OFF" karo to apne aap seekhna band (jo tum khud likhwao wo chalta hai).

## Yaad kahan rakhi hai
Phone/PC ke browser (`localStorage`). Server par kuch save nahi hota (Render free me disk mit jaati hai).
App data clear ya uninstall karne par yaad mit jaayegi, isliye 🧠 > **Backup copy** se kabhi-kabhi copy karke rakh lo, aur **Restore** se wapas lao.

## Tests
```
python -m pytest tests          # server
node tests/mem.test.js          # dimaag
node tests/brain_integration.test.js
node tests/ask_flow.test.js
```
