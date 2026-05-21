"""Google Sheets (service account) + Drive (user OAuth) clients.

Service accounts can't upload to personal Drive (no storage quota), so photo
upload uses the user's OAuth refresh token; sheet writes use the service account.
"""
import io
import json
import os

from google.oauth2 import service_account
from google.oauth2.credentials import Credentials as UserCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

SA_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _sa_credentials():
    raw = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if raw:
        info = json.loads(raw)
        return service_account.Credentials.from_service_account_info(info, scopes=SA_SCOPES)
    path = os.environ.get("GOOGLE_CREDENTIALS_FILE", "service-account.json")
    return service_account.Credentials.from_service_account_file(path, scopes=SA_SCOPES)


def _user_credentials():
    """OAuth user creds for Drive upload — file is owned by the user, no SA quota issue."""
    return UserCredentials(
        token=None,  # forces refresh on first call
        refresh_token=os.environ["OAUTH_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["OAUTH_CLIENT_ID"],
        client_secret=os.environ["OAUTH_CLIENT_SECRET"],
        scopes=["https://www.googleapis.com/auth/drive"],
    )


_sheets = None
_drive = None


def sheets():
    global _sheets
    if _sheets is None:
        _sheets = build("sheets", "v4", credentials=_sa_credentials(), cache_discovery=False)
    return _sheets


def drive():
    global _drive
    if _drive is None:
        _drive = build("drive", "v3", credentials=_user_credentials(), cache_discovery=False)
    return _drive


def ensure_header(sheet_id: str, headers: list):
    """Write headers to row 1 if the sheet is empty."""
    resp = sheets().spreadsheets().values().get(
        spreadsheetId=sheet_id, range="A1:Z1"
    ).execute()
    if not resp.get("values"):
        sheets().spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range="A1",
            valueInputOption="RAW",
            body={"values": [headers]},
        ).execute()


def append_row(sheet_id: str, row: list):
    sheets().spreadsheets().values().append(
        spreadsheetId=sheet_id,
        range="A1",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]},
    ).execute()


def read_rows(sheet_id: str, limit: int = 200) -> list:
    resp = sheets().spreadsheets().values().get(
        spreadsheetId=sheet_id, range="A1:Z10000"
    ).execute()
    values = resp.get("values", [])
    if not values:
        return []
    headers = values[0]
    rows = []
    for v in values[1:]:
        rows.append({headers[i]: (v[i] if i < len(v) else "") for i in range(len(headers))})
    rows.reverse()  # newest first
    return rows[:limit]


def upload_photo(folder_id: str, filename: str, data: bytes, mime: str = "image/jpeg") -> str:
    """Upload bytes to Drive folder, return webViewLink. Simple multipart + 2x retry on transient errors."""
    import time
    for attempt in range(3):
        try:
            media = MediaIoBaseUpload(io.BytesIO(data), mimetype=mime, resumable=False)
            meta = {"name": filename, "parents": [folder_id]}
            f = drive().files().create(
                body=meta, media_body=media, fields="id, webViewLink"
            ).execute()
            drive().permissions().create(
                fileId=f["id"],
                body={"type": "anyone", "role": "reader"},
                fields="id",
            ).execute()
            return f["webViewLink"]
        except Exception:
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise
