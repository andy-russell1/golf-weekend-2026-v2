# Golf Weekend Streamlit App

Standalone Streamlit version of the golf weekend app, extracted for deployment on Streamlit Community Cloud.

## Included scope

- `4-Ball` as net better-ball match play
- `Stroke Play` as net better-ball stroke play
- `Skins` as net better-ball skins with carryovers
- `Singles` as two parallel net singles match-play fixtures worth 1 point each

Seeded weekend lineup:

- `R1` Rolls of Monmouth -> `4-Ball`
- `R2` Clyne -> `Stroke Play`
- `R3` Neath -> `Skins`
- `R4` St Pierre (Old Course) -> `Singles`

## Repo layout

- `app.py` main Streamlit entrypoint and page router
- `pages/` multipage Streamlit views
- `components/` UI sections
- `domain/` golf logic and scoring
- `support/` data loading, session state, app context, Google Sheets integration
- `assets/` CSS
- `golf_trip_data/` course data, metadata, and images

## Local run

Create an environment, install dependencies, then run:

```bash
pip install -r requirements.txt
streamlit run app.py
```

If Google Sheets credentials are not configured, the app falls back to session-local storage. That fallback is useful for demos only: live scores are not shared across users/devices and may be lost on refresh or restart.

## Pre-trip checks

Run the test suite from the repo root:

```bash
pytest
```

Launch locally:

```bash
streamlit run app.py
```

Confirm Google Sheets connection in `Setup / Admin` -> `Connection`. The connection panel should show `Sheets connection OK`; if it does not, confirm the deployed secrets are present and the workbook is shared with the service account email.

Reset a round safely from `Setup / Admin` -> `Admin Actions`. Select the fixture in the sidebar first, tick the confirmation box, type `RESET`, then reset only that selected round.

Score a hole on mobile from `Live Scoring`. The scoring cursor resumes from the saved `scores` rows, so a browser refresh after saving hole 1 should continue at hole 2. Use the minus/plus controls beside each player to set gross scores quickly, check the live preview, then use `Save + Next` or `Save Hole`. Saved complete holes open in a protected viewing state; use `Edit saved hole` before updating workbook rows. A score save is only treated as workbook-saved after the app writes the Google Sheets rows, reads them back, and verifies the expected `round_id`, hole, `player_id`, gross score, and status values.

Live scoring is the quota-sensitive path. The app keeps stable workbook tabs cached and invalidates only the changed worksheet after score/result/player/round/settings saves. The live save flow still performs a fresh readback of the `scores` tab for verification, but it avoids clearing every workbook cache mid-save. If Google returns a quota error during live use, avoid repeated browser refreshes and wait for the per-minute quota window to reset before retrying.

Singles pairings can be set from `Setup / Admin` -> `Round Setup` when `Singles` is selected. The pairings are saved in the existing `settings` tab under `singles_matchups_json`, so no extra worksheet or header is required.

Weekend bonus competitions can be configured from `Setup / Admin` -> `Bonus Points`. The defaults are Longest Drive on Rolls of Monmouth hole 12 and Closest to the Pin on Clyne hole 8. Winners are captured in `Live Scoring` only when the active hole matches the configured bonus hole, and the points are saved in `settings` under `bonus_competitions_json`.

## Product flow

- `Weekend Hub` is the default front door in the sidebar navigation.
- `Live Scoring` is the main on-course workflow; `Full Scorecard Edit` is the secondary correction path.
- `pages/1_Weekend_Hub.py` now owns the hub view so the home page label stays clean in navigation.
- `Setup / Admin` -> `Exports` provides premium PDF scorecard downloads for the selected round or the full weekend pack. The export uses saved gross scores plus the central scoring result, keeping PDF layout separate from scoring logic.

## Streamlit Community Cloud secrets

Add this structure in the app secrets UI:

```toml
[golf_weekend]
workbook_name = "Russell_Kelly_Invitational_2026_google_sheets_ready_v2"
# workbook_id = "optional-google-sheet-id"

[gcp_service_account]
type = "service_account"
project_id = "your-project-id"
private_key_id = "your-private-key-id"
private_key = """-----BEGIN PRIVATE KEY-----
YOUR_KEY
-----END PRIVATE KEY-----"""
client_email = "your-service-account@your-project.iam.gserviceaccount.com"
client_id = "your-client-id"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/your-service-account"
universe_domain = "googleapis.com"
```

## Credential handling

Do not commit Google service-account JSON files, OAuth client files, tokens, PEM files, or `.streamlit/secrets.toml`.

For deployed use, provide credentials through Streamlit Community Cloud secrets or environment-level secret management. The app supports:

- `GOLF_WEEKEND_WORKBOOK_NAME`
- `GOLF_WEEKEND_WORKBOOK_ID`
- `GOLF_WEEKEND_SERVICE_ACCOUNT_FILE` pointing at a secret-managed file outside the repository

Legacy local development can still use this default path, but do not keep real credentials there inside a working repo:

```text
secrets/google_service_account.json
```

Desktop OAuth remains available for local-only development if you provide:

```text
secrets/google_oauth_client.json
```

## Required Google Sheet tabs

The workbook must contain these tabs:

- `players`
- `rounds`
- `scores`
- `results`
- `settings`

The app will seed headers and default rows for `players`, `rounds`, and `settings` when the workbook is reachable.

## Publish checklist

1. Push this folder into its own GitHub repo.
2. Create a Streamlit Community Cloud app pointing at `app.py`.
3. Add the `golf_weekend` and `gcp_service_account` secrets.
4. Share the Google Sheet with the service account email from the secret.
5. Open the deployed app and confirm the connection banner shows `Sheets connection OK`.
6. Verify players, handicaps, and the four default rounds in `Setup / Admin`.
7. Save at least one test hole in each format before live use.

## Troubleshooting Streamlit secrets

- If Setup / Admin says `Streamlit service-account secrets could not be read`, the usual problem is `gcp_service_account.private_key`.
- Paste the full PEM exactly as a TOML multiline string, including `-----BEGIN PRIVATE KEY-----` and `-----END PRIVATE KEY-----`.
- If your key came from JSON with escaped `\n` line breaks, the app now normalizes that format too, but the full key content still needs to be intact.
- A workbook lookup failure is a separate issue. If credentials load correctly but the workbook cannot be opened, share the sheet with the `client_email` from the same secret.

## Notes

- `Stroke Play` and `Skins` are UI labels; both use net better-ball team scoring.
- Each round can use either full playing-handicap shot allocation or relative allocation from the lowest playing handicap. Existing default behaviour is preserved: `4-Ball` and `Singles` default to relative, while `Stroke Play` and `Skins` default to full.
- `Skins` carries tied holes forward to the next outright winner.
- If Google Sheets is unavailable, the UI remains usable in session fallback mode, but state is not shared across users.
- Live scoring should be run against Google Sheets. Session fallback is visibly warned in the app and should not be treated as durable scoring storage.
- Score rows are keyed by `round_id`, hole, and `player_id`. If duplicate rows already exist in Google Sheets, the app reads the latest `updated_at` row and warns the user; it does not automatically delete older duplicate rows.
- The sidebar is the primary page navigation. In-body pages now focus on the current round action instead of repeating a full page-link grid.
- `Setup / Admin` requires an explicit confirmation before the selected round can be reset.
