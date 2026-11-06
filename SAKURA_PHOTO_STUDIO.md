# Sakura Photo Studio (free manual AI handoff)

## Supported workflow

1. Ask Sakura to edit a photo. If no source photo is attached, Sakura opens the Android photo picker (`pick_photo`).
2. Sakura prepares an English edit prompt and asks for confirmation.
3. `ai_create` opens Android's share chooser with the source image and prompt. It does **not** click Send, bypass provider limits, or claim that an edit has completed.
4. Choose an installed AI app (ChatGPT, Gemini, or Claude), review the prompt, and manually press Send. Use only features available in that app's free tier; do not purchase or upgrade.
5. Save the generated image in the AI app to the device.
6. Return to Sakura and say `import edited photo`. `import_edited_photo` opens the picker and copies the selected result into `Pictures/Sakura` in Gallery.
7. Say `compare before after` / `compare photos`. `compare_photos` asks for the original first and edited image second, then opens an offline side-by-side viewer.

## Prompt presets

- Background removal: preserve the requested subject, clean edges, transparent PNG when supported; do not alter identity.
- Object removal: remove only the named object and reconstruct the background naturally.
- Face-preserving retouch: preserve identity, facial geometry, age, expression and natural skin texture.
- HD enhancement: upscale, denoise and sharpen without inventing facial details or changing proportions.

## Honest limitations

- Free quotas and editing/export support vary by provider, account, country and time.
- Sakura cannot guarantee that a provider generated an image. The user must manually send, wait, save and import the result.
- Some apps may not accept a shared image+prompt in one handoff. If that happens, manually attach the original and paste the prompt in that app.
- No AI editing model or paid API is bundled. Sakura's import, Gallery save and comparison steps are local/offline.
