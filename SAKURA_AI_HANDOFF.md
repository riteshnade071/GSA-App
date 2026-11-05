# Photo edit / PDF — free manual AI app handoff

## Photo editing workflow
1. **Source photo**: `pick_photo` opens Android's system photo picker, or `find_photos` searches Gallery albums by date.
2. **Prepare handoff**: `ai_create {kind:"edit", uri, prompt}` asks for confirmation and opens Android's share chooser with the source image and detailed prompt.
3. **Manual send**: Master chooses an installed AI app (ChatGPT, Gemini or Claude), reviews the prompt and presses Send manually. Sakura never guesses or clicks a Send button.
4. **Save result**: after the provider has actually generated the edited image, Master saves it to the phone.
5. **Import result**: `import_edited_photo {}` opens the picker and copies the selected output into Gallery / `Pictures/Sakura`.
6. **Compare**: `compare_photos {}` asks for the original first and edited result second, then opens the offline before/after viewer.

## Prompt presets
- Background removal: preserve only the requested subject, clean edges, transparent PNG if the app supports it; don't change identity.
- Object removal: remove only the named object and reconstruct the background naturally.
- Face-preserving retouch: preserve identity, facial geometry, age, expression and natural skin texture.
- HD enhancement: upscale, denoise and sharpen without inventing details or changing proportions.

## Free-tier and privacy notes
- No paid image API or bundled AI model is used. Free quota, editing features and export support depend on the selected app/account and may change.
- Sakura never purchases, upgrades, presses Send, or claims a generated image exists before Master imports the result.
- The photo is shared with the third-party app only after Master confirms. Review the selected app and its privacy terms before sending sensitive photos.
- If the app cannot accept the shared image+prompt, manually attach the original and paste the prompt.

## Files
- Android: `AiHandoff.kt`, `PickActivity.kt`, `PhotoCompareActivity.kt`, `Tools.kt`, `AndroidManifest.xml`.
- Server: `Umiko-main/main.py` (`TOOL_NAMES` + `TOOLS_TEXT`) and `index.html` (tool timeout + handoff continuation).

## Verification status
- Python backend test suite and Node frontend tests are run in the delivery environment.
- Android Gradle build and on-device behaviour must still be verified through the included GitHub Actions workflow and on the target phone. The current build environment does not contain Android SDK / Gradle, so no APK build is claimed here.
