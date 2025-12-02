import csv
import hashlib
import os
from tempfile import NamedTemporaryFile
from typing import IO, TYPE_CHECKING, Any, Iterator
from zipfile import ZipFile

import requests
from sqlmodel import select
from tqdm import tqdm

from recyoself import USER_DATA_DIR

from .models import Campsite, EntityChecksum, Facility, Organization, RecreationArea

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

    def fetch_entities(self) -> None:
        with NamedTemporaryFile(delete_on_close=False) as tempf:
            self._download_zip(tempf)
            self._extract_entities(tempf)

    def is_entity_csv_updated(self, entity: str, session: "Session") -> bool:
        csv_checksum = self._get_csv_checksum(self._csv_filepath_for(entity))
        checksum_stmt = select(EntityChecksum).where(EntityChecksum.name == entity)
        entity_checksum = session.scalars(checksum_stmt).first()
        if not entity_checksum:
            return True
        return csv_checksum != entity_checksum.checksum

    def make_organizations(self, session: "Session") -> Iterator[Organization]:
        self._update_entity_checksum("Organizations", session)

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
        self._update_entity_checksum("RecAreas", session)

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

    def make_facilities(self, session: "Session") -> Iterator[Facility]:
        self._update_entity_checksum("Facilities", session)

        for data in self._read_csv("Facilities"):
            if not data["FacilityName"]:
                continue

            kwargs = {
                "name": data["FacilityName"],
                "facility_id": data["FacilityID"],
                "type": data["FacilityTypeDescription"],
            }
            # In JSON, "OrgFacilityID" and "ParentOrgID" are switched lol
            org_stmt = select(Organization).where(
                Organization.org_id == data["OrgFacilityID"]
            )
            org = session.scalars(org_stmt).first()
            if not org:
                print(
                    f'Cannot process facility "{kwargs["name"]} ({kwargs["facility_id"]}): Org "{data["OrgFacilityID"]}" not found.'
                )
                continue
            rec_area = None
            rec_area_id = data["ParentRecAreaID"]
            if rec_area_id:
                rec_area_stmt = select(RecreationArea).where(
                    RecreationArea.rec_area_id == rec_area_id
                )
                rec_area = session.scalars(rec_area_stmt).first()

            yield Facility(org=org, rec_area=rec_area, **kwargs)

    def make_campsites(self, session: "Session") -> Iterator[Campsite]:
        self._update_entity_checksum("Campsites", session)

        for data in self._read_csv("Campsites"):
            campsite_type, electric, group_site = self._parse_campsite_type(
                data["CampsiteType"]
            )
            kwargs = {
                "name": data["CampsiteName"],
                "loop": data.get("Loop"),
                "campsite_id": data["CampsiteID"],
                "type": campsite_type,
                "electric": electric,
                "group_site": group_site,
                "use": data["TypeOfUse"],
            }
            facility_stmt = select(Facility).where(
                Facility.facility_id == data["FacilityID"]
            )
            facility = session.scalars(facility_stmt).first()

            yield Campsite(facility=facility, **kwargs)

    def _parse_campsite_type(self, type_str: str) -> tuple[str, bool, bool]:
        electric = False
        group_site = False
        type_parts = type_str.split(" ")

        if type_parts[-1] in ["ELECTRIC", "NONELECTRIC"]:
            # determine electric and remove from parts
            electric = type_parts.pop() == "ELECTRIC"

        if type_parts[0] == "GROUP":
            # determine if group site and remove
            group_site = True
            del type_parts[0]
            if "AREA" in type_parts and type_parts != ["STANDARD", "AREA"]:
                # keep AREA if it's STANDARD AREA
                type_parts.remove("AREA")

        return " ".join(type_parts), electric, group_site

    def _download_zip(self, destination: IO[Any]) -> None:
        response = requests.get(self.entities_csv_zip_url, stream=True)
        chunk_size: int = 1024
        total_size: int = int(response.headers.get("content-length", 0))
        with tqdm(total=total_size, unit="B", unit_scale=True) as progress_bar:
            for chunk in response.iter_content(chunk_size=chunk_size):
                progress_bar.update(len(chunk))
                destination.write(chunk)
            destination.close()
            if total_size != 0 and progress_bar.n != total_size:
                raise RuntimeError("Could not successfully download file")

    def _extract_entities(self, zip_file: IO[Any]) -> None:
        self._ensure_data_dir()
        with ZipFile(zip_file.name, "r") as zp:
            for entity in self.entities:
                csv_filename = f"{entity}_API_v1.csv"
                zp.extract(csv_filename, f"{self.data_dir}")

    def _ensure_data_dir(self):
        os.makedirs(self.data_dir, exist_ok=True)

    def _csv_filepath_for(self, entity: str) -> str:
        return f"{self.data_dir}/{entity}_API_v1.csv"

    def _read_csv(self, entity: str) -> Iterator[dict[str, str]]:
        filepath = self._csv_filepath_for(entity)
        num_lines = self._get_num_records_csv(filepath)
        with open(filepath, "r") as f:
            reader = csv.DictReader(f)
            with tqdm(
                total=num_lines, unit="recs", desc=f"Loading {entity}"
            ) as progress_bar:
                for row in reader:
                    yield row
                    progress_bar.update()

    def _get_num_records_csv(self, filepath: str) -> int:
        with open(filepath, "r") as f:
            reader = csv.reader(f)
            return sum(1 for _ in reader) - 1

    def _get_csv_checksum(self, filepath: str) -> str:
        with open(filepath, "rb") as f:
            digest = hashlib.file_digest(f, "sha256")
        return digest.hexdigest()

    def _update_entity_checksum(self, entity: str, session: "Session") -> None:
        new_checksum = self._get_csv_checksum(self._csv_filepath_for(entity))
        entity_cs_stmt = select(EntityChecksum).where(EntityChecksum.name == entity)
        entity_cs = session.scalars(entity_cs_stmt).first()
        if not entity_cs:
            entity_cs = EntityChecksum(name=entity)
        entity_cs.checksum = new_checksum
        session.add(entity_cs)
