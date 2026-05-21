"""Static config. Drivers + MSCPs are now read from the Google Sheet tabs."""

# Distance threshold for "Far from MSCP" warning + Review status.
FAR_THRESHOLD_METERS = 100

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
