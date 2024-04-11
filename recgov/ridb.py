import csv
import os
from tempfile import NamedTemporaryFile
from typing import IO, Any, Iterator
from zipfile import ZipFile

import requests
from tqdm import tqdm

from recgov import USER_DATA_DIR

from .models import Organization


class RIDB:
    base_url: str = "https://ridb.recreation.gov"
    entities: list[str] = ["Campsites", "Facilities", "Organizations", "RecAreas"]

    @property
    def entities_csv_zip_url(self) -> str:
        return f"{self.base_url}/downloads/RIDBFullExport_V1_CSV.zip"

    @property
    def data_dir(self) -> str:
        return f"{USER_DATA_DIR}/ridb"

    def make_organizations(self) -> Iterator:
        for data in self._read_csv("Organizations"):
            yield Organization(
                name=data["OrgName"],
                abbreviation=data["OrgAbbrevName"],
                org_id=data["OrgID"],
            )

    def fetch_entities(self) -> None:
        with NamedTemporaryFile(delete_on_close=False) as tempf:
            self._download_zip(tempf)
            self._extract_entities(tempf)

    def _download_zip(self, destination: IO[Any]) -> None:
        response = requests.get(self.entities_csv_zip_url, stream=True)
        chunk_size: int = 1024
        total_size: int = int(response.headers.get("content-length", 0))
        print(f"=== Downloading full RIDB CSV zip...")
        with tqdm(total=total_size, unit="B", unit_scale=True) as progress_bar:
            for chunk in response.iter_content(chunk_size=chunk_size):
                progress_bar.update(len(chunk))
                destination.write(chunk)
            destination.close()
            if total_size != 0 and progress_bar.n != total_size:
                raise RuntimeError("Could not successfully download file")

    def _extract_entities(self, zip_file: IO[Any]) -> None:
        print(f"=== Extracting relevant entity CSVs from zip to {self.data_dir}...")
        self._ensure_data_dir()
        with ZipFile(zip_file.name, "r") as zp:
            for entity in self.entities:
                csv_filename = f"{entity}_API_v1.csv"
                zp.extract(csv_filename, f"{self.data_dir}")

    def _ensure_data_dir(self):
        os.makedirs(self.data_dir, exist_ok=True)

    def _read_csv(self, entity: str) -> Iterator[dict[str, str]]:
        with open(f"{self.data_dir}/{entity}_API_v1.csv", "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                yield row
