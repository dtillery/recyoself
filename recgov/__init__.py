import os

from platformdirs import PlatformDirs
from prompt_toolkit.styles import Style

if os.environ.get("RECGOV_ENV") == "dev":
    USER_DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data"))
else:
    LOCAL_DIRS = PlatformDirs(appname="recgov", appauthor=False, ensure_exists=True)
    USER_DATA_DIR = LOCAL_DIRS.user_data_dir

USER_AGENT: str = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15"
)
HEADERS: dict = {"user-agent": USER_AGENT}

# stolen from https://github.com/tmbo/questionary/blob/master/examples/autocomplete_ants.py
AUTOCOMPLETE_STYLE = Style(
    [
        ("separator", "fg:#cc5454"),
        ("qmark", "fg:#673ab7 bold"),
        ("question", ""),
        ("selected", "fg:#cc5454"),
        ("pointer", "fg:#673ab7 bold"),
        ("highlighted", "fg:#673ab7 bold"),
        ("answer", "fg:#f44336 bold"),
        ("text", "fg:#FBE9E7"),
        ("disabled", "fg:#858585 italic"),
    ]
)
