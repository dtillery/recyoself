import csv
import os
from tempfile import NamedTemporaryFile
from typing import IO, TYPE_CHECKING, Any, Iterator
from zipfile import ZipFile

import requests
from sqlmodel import select
from tqdm import tqdm

from recgov import USER_DATA_DIR

from .models import Organization, RecreationArea

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class RIDB:
    base_url: str = "https://ridb.recreation.gov"
    entities: list[str] = ["Campsites", "Facilities", "Organizations", "RecAreas"]

    @property
    def entities_csv_zip_url(self) -> str:
        return f"{self.base_url}/downloads/RIDBFullExport_V1_CSV.zip"

    @property
    def data_dir(self) -> str:
        return f"{USER_DATA_DIR}/ridb"

    def make_organizations(self) -> Iterator[Organization]:
        for data in self._read_csv("Organizations"):
            yield Organization(
                name=data["OrgName"],
                abbr=data["OrgAbbrevName"],
                org_id=data["OrgID"],
            )

    def make_org_157(self) -> Organization:
        """There exists an Organization with ID 157 that does not appear in RIDB
        Organization-exports but is referenced in other entities. Considering that many
        Departments of X refer to it as their ParentOrg, I am going to assume it's
        equivalent to the US Government for our purposes."""

        return Organization(name="US Government", abbr="USA", org_id="157")

    def make_rec_areas(self, session: "Session") -> Iterator[RecreationArea]:
        for data in self._read_csv("RecAreas"):
            kwargs = {
                "name": data["RecAreaName"],
                "org_rec_area_id": data["OrgRecAreaID"],
                "rec_area_id": data["RecAreaID"],
            }

            org_stmt = select(Organization).where(
                Organization.org_id == data["ParentOrgID"]
            )
            org = session.scalars(org_stmt).first()
            yield RecreationArea(org=org, **kwargs)

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
