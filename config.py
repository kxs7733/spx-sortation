"""Static config — dummy seeds for drivers, agencies, MSCPs."""

DRIVERS = ["DRV-001", "DRV-002", "DRV-003"]

AGENCIES = ["5G MAX", "Concept"]

# Dummy MSCP locations — real-ish Singapore HDB multi-storey carpark coordinates.
# Replace with the real list when SPX provides it.
MSCPS = [
    {"id": "MSCP-001", "name": "Ang Mo Kio Ave 6 MSCP", "lat": 1.37553, "lon": 103.85120},
    {"id": "MSCP-002", "name": "Bedok North Ave 3 MSCP", "lat": 1.33470, "lon": 103.93210},
    {"id": "MSCP-003", "name": "Jurong West St 81 MSCP", "lat": 1.34110, "lon": 103.70960},
]

# Distance threshold for "Far from MSCP" warning + Review status.
FAR_THRESHOLD_METERS = 200

SHEET_HEADERS = [
    "Driver ID",
    "Agency",
    "MSCP ID",
    "Timestamp",
    "Lat",
    "Long",
    "Address",
    "Distance to MSCP (m)",
    "Status",
    "Photo Link",
]
