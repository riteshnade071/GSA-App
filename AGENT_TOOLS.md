# Tools ab server ke main.py me hain

Alag se kuch register nahi karna. Umiko repo ka naya main.py (TOOL_NAMES + TOOLS_TEXT) sab jaanta hai.

Android app ye tools chalati hai (page ke agent loop ke hisaab se):
read_screen, tap {id}, type_text {id,text,enter}, scroll {dir,speed,times}, auto_scroll, stop_agent,
close_app, toggle_setting, go_back, go_home, press_key.

Natije ka dhaancha (page ise padhti hai): {"ok":true,"screen":{"app":"...","items":["1|button|Search","2|edit|..."]}}
Bank/UPI/password/OTP wali screen par: {"ok":false,"sensitive":true}. Accessibility OFF ho to: {"needs_access":true}. Ruk jao par: {"cancelled":true}.

Photo Studio tools:
- `pick_photo {}` selects the original image.
- `ai_create {kind:"edit", uri, prompt}` opens a manual share chooser after confirmation; Master sends manually.
- `import_edited_photo {}` selects the generated output and saves it to Gallery `Pictures/Sakura`.
- `compare_photos {}` selects original then edited image and opens an offline comparison view.
