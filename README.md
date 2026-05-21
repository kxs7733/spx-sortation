# SPX Sortation — Proof-of-Sortation Webapp

A mobile webapp that SPX drivers open on their phone to prove they sorted parcels at an approved Multi-Storey Car Park (MSCP) instead of an HDB void deck. Each submission captures the driver's identity, current GPS location, a photo of the sorting site, and the MSCP they claim to be at, then writes everything to a Google Sheet with a status flag (`Valid` or `Review`) based on how far they actually are from the MSCP they picked.

The whole thing is a single Flask app deployed to Railway. The Google Sheet is both the **operational data store** (submissions are logged here for SPX supervisors to review) and the **configuration store** (the supervisor edits Drivers and MSCPs in the same sheet — no code changes needed to add a new driver or carpark).

---

## Quick links

| Resource | URL |
|---|---|
| Live app | https://web-production-spxsort.up.railway.app/ |
| Source code | https://github.com/kxs7733/spx-sortation |
| Operational sheet | https://docs.google.com/spreadsheets/d/1eLw6DmMzJpsO4BoRvxXkh6tvjM_p_mEWBXfch0iRrM0 |
| Photo Drive folder | `1kdMQe86xvl0NDJvm0hYiIB05y-x4jXOf` (under Shopee Workspace, shared with personal Gmail for upload) |

---

## How a driver uses it

1. Driver opens the app URL on their phone (Safari/Chrome both work; the URL is HTTPS so geolocation is allowed).
2. The header shows today's date and which tab they're on (**Submit** by default, with **History** alongside).
3. The **LOCATION** card auto-fills:
   - Address resolved from current GPS via OneMap reverse-geocode (e.g. `Blk 171 Paya Lebar Road`)
   - A subtitle showing distance to the MSCP they pick (e.g. `45m from Blk 18A Lorong 6 Toa Payoh`)
   - An orange **Far from MSCP** chip appears in the corner if the driver is >100 m from the MSCP they selected
4. They pick three things, in any order:
   - **Driver** — dropdown shows the driver's name (e.g. "Mr 1"), submits the canonical Driver ID
   - **Agency** — auto-populates from the chosen driver (read-only)
   - **MSCP Address** — dropdown shows the block + road of each MSCP, submits the canonical MSCP ID
5. They tap **SORTATION PHOTO** → camera opens → snap. The image is compressed in-browser to ~300 KB before upload so submissions are fast and reliable on 4G.
6. **Submit Sortation Check** activates only when all required fields are filled (GPS, photo, driver, MSCP). On tap, the photo uploads to Drive, the row appends to the sheet, and a toast confirms "Submitted — Valid" or "Submitted — Review".
7. The **History** tab shows their recent submissions with the same `Valid` / `Review` chip the supervisor sees in the sheet.

The whole flow takes ~30–45 seconds per driver per day.

---

## How a supervisor manages it

Everything a supervisor needs to change is in the Google Sheet — no code, no deploys.

### Sheet tabs

| Tab | Purpose | Edit cadence |
|---|---|---|
| `Sheet1` | Submissions log (driver, agency, MSCP, timestamp, lat/long, address, distance, status, photo link). The app writes here — supervisors only **read** this tab. | Read-only |
| `Drivers` | Roster. Columns: `Driver ID`, `Driver Name`, `Agency`. The app's driver dropdown is populated from here. | When onboarding or removing drivers |
| `MSCP` | Approved sortation sites. Columns: `MSCP ID`, `Lat`, `Long`, `Address`. The app uses Lat/Long to verify whether the driver is actually close to the MSCP they claim. | When adding/removing approved sites |

### Adding a driver
Open the **Drivers** tab. Add a row: `DRV-004 | Mr 4 | 5G MAX`. That's it. Within ~60 seconds the new driver appears in the app's dropdown (60 s is the seed cache TTL).

### Adding an MSCP
Open the **MSCP** tab. Add a row with a unique `MSCP ID` (e.g. `MSCP-006`), the **latitude** and **longitude** (decimal degrees, ~6–7 decimals), and the human-readable **Address**. The lat/long can be sourced from the official HDB carpark dataset on data.gov.sg, or by dropping a pin on Google Maps and copying coordinates. Without lat/long, the MSCP still appears in the dropdown but distance can't be verified — any submission against it is automatically flagged `Review`.

### Validating submissions
Scroll the main log (`Sheet1`). Any row with `Status = Review` and a non-empty `Distance to MSCP (m)` >100 means the driver's GPS was further from the chosen MSCP than the threshold. Open the photo link to see whether they were genuinely sorting at the right place. Adjust workflow with the driver as needed.

---

## Architecture

```
                  ┌─────────────────────────────────────────┐
                  │   Driver's phone (Safari / Chrome)       │
                  │   - Geolocation API                      │
                  │   - Camera capture                       │
                  │   - In-browser JPEG compression          │
                  └────────────────┬────────────────────────┘
                                   │ HTTPS (Railway-issued)
                                   ▼
                  ┌─────────────────────────────────────────┐
                  │   Flask app on Railway                  │
                  │   - / serves the SPA                    │
                  │   - /api/seed reads Drivers + MSCPs     │
                  │   - /api/geocode → OneMap revgeocode    │
                  │   - /api/submit → Drive + Sheets        │
                  │   - /api/history reads Sheet1            │
                  │   - 60s in-memory cache on seed         │
                  └──────┬─────────────────┬────────────────┘
                         │                 │
            Sheets API   │                 │   Drive API
       (service account, │                 │  (user OAuth — your
        Sheets scope)    │                 │   personal Gmail)
                         ▼                 ▼
              ┌──────────────────┐    ┌────────────────────┐
              │  Google Sheet     │    │  Google Drive folder│
              │  - Sheet1 (log)   │    │  - Photos owned by  │
              │  - Drivers         │    │    kwangxiong@      │
              │  - MSCP            │    │    gmail.com        │
              └──────────────────┘    │  - "Anyone with link│
                                       │     can view" set    │
                                       │     per upload       │
                                       └────────────────────┘
```

**Two different Google identities are used on purpose:**

- **Sheets** uses a **service account** — it's stable, has no quota issue for sheet rows, and avoids OAuth refresh complexity. The service account is added as Editor on the sheet.
- **Drive** uses **OAuth user credentials** (`kwangxiong@gmail.com` personal Gmail) because **service accounts cannot upload to personal Drive** — they have no storage quota (a Google policy change in 2022). Files uploaded via OAuth are owned by the user account, which has plenty of quota.

If SPX later moves to a Google Workspace Shared Drive, the Drive upload can be switched back to the service account using `supportsAllDrives=True`.

---

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Server | Flask + gunicorn | Tiny, single-file, easy to deploy on Railway |
| Frontend | Vanilla HTML/CSS/JS | No build step, no framework, 3 files (`index.html`, `style.css`, `app.js`) |
| Geocoding | OneMap (gov.sg) | Free, accurate for Singapore HDB addresses; Bearer-token auth (3-day TTL) |
| Storage | Google Sheets + Drive | Familiar to SPX supervisors, no extra database to operate |
| Hosting | Railway | Auto-deploys from GitHub `main`; free HTTPS domain |

Dependencies live in `requirements.txt`. The only ones that matter operationally: `flask`, `gunicorn`, `google-api-python-client`, `google-auth`, `requests`.

---

## Environment variables

All of these are set in **Railway → your service → Variables**. They're also read locally from process environment if you run the app on your laptop.

| Name | Purpose | Source |
|---|---|---|
| `SHEET_ID` | The operational Google Sheet | The `/d/<id>/edit` part of the sheet URL |
| `DRIVE_FOLDER_ID` | Drive folder where photos go | The `/folders/<id>` part of the folder URL |
| `GOOGLE_CREDENTIALS_JSON` | Service-account JSON (used for Sheets only) | Contents of the `service-account.json` file, pasted as one line |
| `OAUTH_CLIENT_ID` | OAuth client ID for Drive upload | From the `google-personal` MCP creds (`~/.workspace-mcp-personal/kwangxiong@gmail.com.json`) |
| `OAUTH_CLIENT_SECRET` | OAuth client secret | Same file |
| `OAUTH_REFRESH_TOKEN` | Long-lived refresh token to mint Drive access tokens | Same file |
| `ONEMAP_EMAIL` | OneMap account email (for reverse-geocode auth) | Whatever email you registered at https://www.onemap.gov.sg/apidocs/register |
| `ONEMAP_PASSWORD` | OneMap account password | Same |
| `PORT` | (Railway sets automatically) Port to bind | Don't set manually |

Whitespace around these values is stripped at runtime — but it's still cleaner to paste them without leading/trailing spaces.

---

## Sheet schema (for reference)

### `Sheet1` — submissions log (the app appends here)

| Column | Notes |
|---|---|
| Driver ID | e.g. `DRV-001` (canonical, not the name) |
| Agency | Derived from the Drivers tab at submission time |
| MSCP ID | e.g. `MSCP-001` (canonical, not the address) |
| Timestamp | SGT, `YYYY-MM-DD HH:MM:SS` |
| Lat | Driver's GPS latitude at submission |
| Long | Driver's GPS longitude at submission |
| Address | OneMap reverse-geocode of the driver's GPS (e.g. `Blk 171 Paya Lebar Road S409048`) |
| Distance to MSCP (m) | Haversine distance from the driver's GPS to the lat/long of the MSCP they picked. Empty if that MSCP has no lat/long. |
| Status | `Valid` if distance ≤100 m, else `Review`. Always `Review` if distance can't be computed. |
| Photo Link | Drive `webViewLink` (anyone with link can view) |

### `Drivers`

`Driver ID | Driver Name | Agency` — header row + one row per driver.

### `MSCP`

`MSCP ID | Lat | Long | Address` — header row + one row per approved sortation site.

---

## Running locally

You'll need Python 3.9+ and the same env vars as Railway. The simplest local flow uses the service-account JSON as a file rather than an env var.

```bash
cd "/path/to/SPX proof of sorting/app"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Service account JSON next to app.py (NOT committed — see .gitignore)
# File should be named service-account.json

# Then run:
PORT=5050 \
SHEET_ID=1eLw6DmMzJpsO4BoRvxXkh6tvjM_p_mEWBXfch0iRrM0 \
DRIVE_FOLDER_ID=1kdMQe86xvl0NDJvm0hYiIB05y-x4jXOf \
ONEMAP_EMAIL='your.email@example.com' \
ONEMAP_PASSWORD='your-password' \
OAUTH_CLIENT_ID='...' \
OAUTH_CLIENT_SECRET='...' \
OAUTH_REFRESH_TOKEN='...' \
python app.py
```

Open http://localhost:5050. A few caveats when running locally:
- macOS Sonoma+ grabs port 5000 for AirPlay Receiver — use 5050 (or anything else).
- Geolocation requires HTTPS on most modern mobile browsers, so you can't test phone-based geo against `http://localhost`. For real device testing, just use the Railway URL.

---

## Deploying to Railway

The repo is connected to Railway. Any push to `main` on GitHub triggers an automatic redeploy (~30–60 s build, then live). To change a variable without code changes, just edit it in Railway → Variables. Railway will auto-restart.

If you ever need to rebuild from scratch:

1. Create a new Railway project → **Deploy from GitHub repo** → `kxs7733/spx-sortation`
2. Add all the env vars from the table above
3. Settings → Networking → Generate Domain

---

## Operational tasks (quick recipes)

### "Add a new driver"
Edit the **Drivers** tab. Add a row `DRV-XXX | Name | Agency`. Driver shows up in the app within 60 s.

### "Add a new MSCP"
Edit the **MSCP** tab. Add a row `MSCP-XXX | <lat> | <lon> | <address>`. To get accurate coords, the fastest way is to use the data.gov.sg HDB carpark dataset (search by car park number, convert SVY21 → WGS84 via the OneMap conversion API). The 5 seed MSCPs currently in the sheet were populated this way.

### "Tune the 'Far from MSCP' threshold"
Edit `FAR_THRESHOLD_METERS` in `config.py`. Currently 100 m. Commit + push — Railway redeploys.

### "The OneMap token isn't working"
Most likely causes (in order):
1. The Railway env var has a trailing space — strip it.
2. The OneMap account password was rotated externally — update Railway.
3. The OneMap account got disabled — check by logging in at https://www.onemap.gov.sg/apidocs/.

If reverse-geocoding fails for any reason, the app degrades gracefully: it still logs the submission, just with an empty `Address` column.

### "Delete the test rows in Sheet1"
There are a handful of dummy rows from initial development (timestamps 2026-05-15 through 2026-05-20, statuses `Valid`/`Review` for `DRV-001/002/003`). Safe to delete manually. The app doesn't care about row order.

### "Rotate the OneMap password"
Change the password on the OneMap site. Update `ONEMAP_PASSWORD` in Railway. The app picks it up on the next request — no restart needed beyond Railway's auto-restart on var change.

### "Move photos to a Workspace Shared Drive"
If SPX provides a Workspace Shared Drive in future, the Drive upload can revert to using the service account (cleaner, no user OAuth needed):
1. Add the service account email as a member of the Shared Drive
2. Set `DRIVE_FOLDER_ID` to the new folder ID
3. In `google_io.py`, change `drive()` to use `_sa_credentials()` instead of `_user_credentials()`, and add `supportsAllDrives=True` + `driveId=<shared-drive-id>` to the `files().create()` and `permissions().create()` calls
4. Remove the three `OAUTH_*` env vars from Railway

---

## Performance notes

- A typical submission round-trip is 3–5 seconds on 4G. Breakdown:
  - Browser-side image compression: ~0.5 s (depends on phone)
  - Upload to Railway: ~1 s for the ~300 KB compressed JPEG
  - Railway → Drive simple multipart upload: ~1–2 s
  - Drive permission update (make link viewable): ~0.5 s
  - OneMap reverse-geocode: ~0.5 s (cached for nothing — fresh each submit)
  - Sheets append: ~0.5 s
- Photo compression target: 1600 px on the long edge, JPEG quality 0.82. Drops a typical iPhone 4 MB shot to ~300 KB with no visible quality loss for plate-sized objects.
- The Drive upload has a 2× retry built in for transient SSL drops (a flaky Railway→Google route we saw once during testing).
- Seed (Drivers + MSCPs) is cached in-process for 60 s. This means supervisor edits take up to a minute to propagate to the app. Acceptable for this use case.

---

## Security notes

- `service-account.json` is in `.gitignore` — never commit. Only paste into Railway as `GOOGLE_CREDENTIALS_JSON`.
- The OAuth refresh token grants full Drive access to your personal Gmail. Treat it like a password. If leaked, revoke it via https://myaccount.google.com/permissions.
- The OneMap password was shared via this project's setup. Consider rotating it after deployment is stable.
- Photos are made "anyone with link can view" on upload so that the link in the sheet works without supervisor login. If you'd prefer stricter access, change `upload_photo()` in `google_io.py` to skip the permission update — but the sheet's Photo Link column will then require a logged-in viewer with folder access.

---

## Known limitations / future work

- **No driver authentication** — anyone with the URL can pick any name from the dropdown. Fine for an honor-system rollout; if SPX needs real auth later, add a simple PIN or SSO layer.
- **No photo deduplication or anti-spoofing** — a driver could re-use yesterday's photo. Possible future: server-side EXIF check that the photo was taken in the last N minutes.
- **No bulk export of submissions** — supervisors do it manually from Google Sheets. Probably fine.
- **No multilingual UI** — currently English only. Driver names/MSCP addresses can be any language, but labels are English.
- **OneMap token cache is process-local** — when Railway restarts the dyno, a fresh OneMap token is minted on the next reverse-geocode call. Minor cost; no behavioral issue.

---

## File guide

| File | What's in it |
|---|---|
| `app.py` | Flask routes + submission orchestration |
| `google_io.py` | Sheets + Drive clients, seed cache, photo upload |
| `geo.py` | OneMap reverse-geocode, haversine distance |
| `config.py` | `FAR_THRESHOLD_METERS` and the sheet's header order |
| `templates/index.html` | The single-page UI |
| `static/style.css` | All styling (mobile-first, ~200 lines) |
| `static/app.js` | All frontend logic (~200 lines) |
| `Procfile` | Tells Railway how to start: `gunicorn app:app` |
| `requirements.txt` | Python deps |
| `runtime.txt` | Python version pin |

That's the whole app — under 1000 lines including HTML and CSS.
