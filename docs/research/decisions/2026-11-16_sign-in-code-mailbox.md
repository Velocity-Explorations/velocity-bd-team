# How the scanner reads Vulcan SOF's emailed sign-in code

16 Nov 2026. Vulcan SOF run 103 failed at login. It was the first scheduled run Vulcan asked for an emailed six-digit
code, and Gmail rejected the app password the scanner reads that mailbox with ("[AUTHENTICATIONFAILED] Invalid
credentials"). Vulcan sends the code to the Vulcan login's own address, the mailbox the IMAP path signs in to.
David asked which way would run without issues once the scanner moves to Velocity's GKE.

## Options compared

| | Gmail API, service account (chosen) | App password over IMAP (in use meanwhile) | gog CLI |
|---|---|---|---|
| Sign-in | The service account in GOOGLE_SERVICE_ACCOUNT_FILE, domain-wide delegation, gmail.readonly | A 16-letter Google app password | A user OAuth sign-in in a browser |
| Breaks when | An admin revokes the grant | Anyone changes that account's Google password, or the admin disables app passwords | The refresh token is revoked (a password change does, for Gmail scopes) |
| On GKE | Headless; Workload Identity can remove the key file | One Kubernetes secret | Wants a desktop keyring and a browser; poor fit |
| Setup | Super admin: Gmail API on in the Cloud project, the client id granted gmail.readonly | 2 minutes at myaccount.google.com/apppasswords, needs 2-Step Verification | 20 to 30 minutes: a Cloud project, an Internal consent screen, a Desktop OAuth client, then `gog auth` |

Findings along the way:
- gog ships no OAuth client of its own.
- An External OAuth app in Testing issues refresh tokens that expire after seven days.
- The scanner's gog code used `gog gmail read`, which current gog no longer has, and passed VULCAN_OTP_MAILBOX as the account, which is not an address. The gog path would need updating if it is ever used.
- The account's normal password never works for IMAP. Gmail answers "Application-specific password required".

## Decision

The Gmail API through the service account (#179): nothing to change or revoke with a password, and keyless on GKE.
The grant reaches every mailbox in the Workspace, read-only, so the key file is the thing to protect. David is not a
super admin, so the app password carries the scanner until the grant is made (docs/RUNBOOK.md, Reading the code
through the Gmail API). A refused mailbox now ends the wait at once and says which step to take (#177).

On GKE a fresh container may not keep Vulcan's cookies, and Vulcan would then ask for a code on every scan, so its
cookie file belongs on a persistent volume.
