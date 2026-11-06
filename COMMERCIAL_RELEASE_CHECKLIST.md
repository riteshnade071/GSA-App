# Sakura Android Commercial Release Checklist

## Completed in this foundation update
- Debug and release builds now have separate cleartext-network policies: debug permits local development HTTP; release disables cleartext traffic.
- Server URL entry defaults to HTTPS unless the developer explicitly types an HTTP URL (intended for debug/local development only).
- Release signing can be supplied via Gradle properties; no production signing key is committed.
- Repository ignore rules cover local environment files, keystores and build outputs.
- The old committed debug keystore has been removed.

## Required before public distribution
- Generate a private production keystore, keep at least two secure backups, and configure CI secrets. Never send it to customers or commit it.
- Replace shared `ACCESS_CODE` with account authentication and per-user authorization.
- Review AccessibilityService, notification listener, overlay, microphone, contacts and all-files access against current Google Play policies. Remove capabilities not essential to the advertised core experience.
- Add a clear permission education screen and just-in-time consent for sensitive capabilities.
- Add privacy policy, terms, subscription terms, data deletion and support links.
- Add Play Billing if selling digital subscriptions through Google Play, subject to current Play policy and eligible alternative billing rules. For direct web sales, review applicable store policies before linking out.
- Build and test a signed Android App Bundle on a real device matrix; verify upgrades preserve data and signing identity.
- Run accessibility, battery, crash, network-loss, account deletion and subscription-expiry tests.

## Current status
This is a release-hardening baseline, not a store-ready build. Authentication, payments, account isolation, policy review, production signing and device testing remain open gates.

## Phase 1 Google account setup
- [ ] Configure Google Cloud OAuth Web Client ID and Android OAuth client.
- [ ] Add debug and production signing SHA-1 fingerprints for `com.sakura.assistant`.
- [ ] Replace `google_web_client_id` in `app/src/main/res/values/strings.xml` with the Web Client ID.
- [ ] Set backend `GOOGLE_CLIENT_ID`, `SAKURA_SESSION_SECRET`, `SAKURA_ENV=production` and persistent `SAKURA_AUTH_DB` path.
- [ ] Test Android Credential Manager and browser Google sign-in using real OAuth configuration.
- [ ] Confirm local memory remains on-device and does not sync across devices.
