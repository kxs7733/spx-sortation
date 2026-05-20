# SPX Sortation — proof-of-sorting webapp

Mobile webapp for SPX drivers to upload a photo + location of where they sorted parcels.
Writes every submission to a Google Sheet, uploads the photo to a Google Drive folder.

## Stack
- Flask + gunicorn
- Google Sheets API + Drive API (service account)
- OneMap reverse-geocode (requires free account at https://www.onemap.gov.sg/apidocs/register)
- Vanilla JS frontend, mobile-first

## One-time setup

### 1. Create a Google service account
1. Go to https://console.cloud.google.com/iam-admin/serviceaccounts
2. Pick or create a project, click **Create Service Account**
3. After creation, open it → **Keys** → **Add key → JSON**. Save the file as `service-account.json` next to `app.py`
4. Enable APIs in the project: **Google Sheets API** + **Google Drive API**

### 2. Share resources with the service account
The JSON includes a `client_email` like `xxx@yyy.iam.gserviceaccount.com`.
- Open the sheet `https://docs.google.com/spreadsheets/d/1eLw6DmMzJpsO4BoRvxXkh6tvjM_p_mEWBXfch0iRrM0/edit` → Share → add that email as **Editor**
- Create a Drive folder for photos → Share → add the email as **Editor** → copy the folder ID from the URL (`/folders/<ID>`)

### 3. Local run
```bash
cd app
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export SHEET_ID=1eLw6DmMzJpsO4BoRvxXkh6tvjM_p_mEWBXfch0iRrM0
export DRIVE_FOLDER_ID=<your folder id>
python app.py
```
Open http://localhost:5000 — note that geolocation requires HTTPS on most phones, so for real device testing use the Railway deploy.

### 4. Railway deploy
1. `git init && git add . && git commit -m "init"` and push to a GitHub repo
2. railway.app → New Project → Deploy from GitHub → pick the repo
3. In Variables, set:
   - `SHEET_ID` = `1eLw6DmMzJpsO4BoRvxXkh6tvjM_p_mEWBXfch0iRrM0`
   - `DRIVE_FOLDER_ID` = your folder id
   - `GOOGLE_CREDENTIALS_JSON` = paste the **entire** service-account.json contents (one line is fine)
   - `ONEMAP_EMAIL` = your OneMap account email
   - `ONEMAP_PASSWORD` = your OneMap account password
4. Railway auto-detects Python + Procfile and assigns a public HTTPS URL — open on your phone

## Endpoints
- `GET /` — webapp
- `GET /api/seed` — drivers, agencies, MSCPs, threshold
- `GET /api/geocode?lat=&lon=` — reverse geocode + nearest MSCP + far flag
- `POST /api/submit` — multipart: driver_id, agency, mscp_id, lat, lon, photo
- `GET /api/history` — last 200 submissions (newest first), optional `?driver_id=`

## Sheet columns
`Driver ID · Agency · MSCP ID · Timestamp · Lat · Long · Address · Distance to MSCP (m) · Status · Photo Link`

`Status` is `Valid` if within `FAR_THRESHOLD_METERS` of the chosen MSCP, else `Review` (tune in `config.py`).

## Dummy seeds (replace later)
- Drivers: `DRV-001, DRV-002, DRV-003`
- Agencies: `5G MAX, Concept`
- MSCPs: 3 real-ish Singapore coords in `config.py` — swap to the actual SPX list when available
