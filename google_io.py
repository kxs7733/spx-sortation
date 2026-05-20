"""Google Sheets + Drive client via service account."""
import io
import json
import os

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _credentials():
    raw = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if raw:
        info = json.loads(raw)
        return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    path = os.environ.get("GOOGLE_CREDENTIALS_FILE", "service-account.json")
    return service_account.Credentials.from_service_account_file(path, scopes=SCOPES)


_sheets = None
_drive = None


def sheets():
    global _sheets
    if _sheets is None:
        _sheets = build("sheets", "v4", credentials=_credentials(), cache_discovery=False)
    return _sheets


def drive():
    global _drive
    if _drive is None:
        _drive = build("drive", "v3", credentials=_credentials(), cache_discovery=False)
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
    """Upload bytes to Drive folder, return webViewLink."""
    media = MediaIoBaseUpload(io.BytesIO(data), mimetype=mime, resumable=False)
    meta = {"name": filename, "parents": [folder_id]}
    f = drive().files().create(
        body=meta, media_body=media, fields="id, webViewLink"
    ).execute()
    # Make readable by anyone with the link.
    drive().permissions().create(
        fileId=f["id"],
        body={"type": "anyone", "role": "reader"},
        fields="id",
    ).execute()
    return f["webViewLink"]
