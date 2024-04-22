import os

from platformdirs import PlatformDirs

if os.environ.get("RECGOV_ENV") == "dev":
    USER_DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data"))
else:
    LOCAL_DIRS = PlatformDirs(appname="recgov", appauthor=False, ensure_exists=True)
    USER_DATA_DIR = LOCAL_DIRS.user_data_dir

USER_AGENT: str = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15"
)
HEADERS: dict = {"user-agent": USER_AGENT}
