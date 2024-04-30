import logging
import os
from typing import Iterator, Optional

import click
import requests

# from recyoself.cli import list_itineraries

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def run(event: dict, context: dict) -> None:
    # ctx = click.Context(list_itineraries)
    # ctx.invoke(list_itineraries)
    url = f"http://localhost:2773/systemsmanager/parameters/get"
    params = {"name": "/test", "withDecryption": "true"}
    headers = {"X-Aws-Parameters-Secrets-Token": os.environ.get("AWS_SESSION_TOKEN")}
    r = requests.get(url, params=params, headers=headers)
    r.raise_for_status()
    logger.info(r.text)


if __name__ == "__main__":
    event = {"facility_id": "4675321"}
    context: dict[str, str] = {}
    run(event, context)
