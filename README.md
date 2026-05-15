# Golf Weekend Streamlit App

Standalone Streamlit version of the golf weekend app, extracted for deployment on Streamlit Community Cloud.

## Included scope

- `4-Ball` as net better-ball match play
- `Stroke Play` as net better-ball stroke play
- `Skins` as net better-ball skins with carryovers
- `Singles` as net singles match play

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

If Google Sheets credentials are not configured, the app falls back to session-local storage.

## Product flow

- `Weekend Hub` is the default front door in the sidebar navigation.
- `Live Scoring` is the main on-course workflow; `Full Scorecard Edit` is the secondary correction path.
- `pages/1_Weekend_Hub.py` now owns the hub view so the home page label stays clean in navigation.

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

## Local credential fallbacks

The app also supports:

- `GOLF_WEEKEND_WORKBOOK_NAME`
- `GOLF_WEEKEND_WORKBOOK_ID`
- `GOLF_WEEKEND_SERVICE_ACCOUNT_FILE`

Default local service account path:

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
- `Skins` carries tied holes forward to the next outright winner.
- If Google Sheets is unavailable, the UI remains usable in session fallback mode, but state is not shared across users.
- The sidebar is the primary page navigation. In-body pages now focus on the current round action instead of repeating a full page-link grid.
- `Setup / Admin` requires an explicit confirmation before the selected round can be reset.
