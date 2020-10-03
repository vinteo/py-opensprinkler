import os

URL = os.environ.get("CONTROLLER_URL") or "http://localhost:8080"
PASSWORD = os.environ.get("CONTROLLER_PASSWORD") or "opendoor"
FIRMWARE_VERSION = float(os.environ.get("CONTROLLER_FIRMWARE") or "219")
