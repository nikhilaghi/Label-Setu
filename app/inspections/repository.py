from datetime import datetime
from typing import List, Optional

from pymongo import ReturnDocument

from app.database import get_db
from app.inspections.models import Inspection


class InspectionRepository:
    def __init__(self):
        self.collection = get_db()["inspections"]
        self.counters = get_db()["counters"]

    def next_id(self) -> str:
        year = datetime.utcnow().year

        counter = self.counters.find_one_and_update(
            {"_id": "inspection"},
            {"$inc": {"seq": 1}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )

        seq = counter["seq"]
        return f"LM-{year}-{seq:04d}"

    def create(self, inspection: Inspection) -> Inspection:
        document = inspection.model_dump(mode="json")
        self.collection.insert_one(document)
        return inspection

    def get(self, inspection_id: str) -> Optional[Inspection]:
        document = self.collection.find_one(
            {"inspectionId": inspection_id},
            {"_id": 0},
        )

        if not document:
            return None

        return Inspection.model_validate(document)

    def update(self, inspection: Inspection) -> Inspection:
        document = inspection.model_dump(mode="json")

        self.collection.replace_one(
            {"inspectionId": inspection.inspectionId},
            document,
            upsert=True,
        )

        return inspection

    def list_all(self) -> List[Inspection]:
        documents = self.collection.find(
            {},
            {"_id": 0},
        ).sort("timestamp", -1)

        return [
            Inspection.model_validate(document)
            for document in documents
        ]

    def delete(self, inspection_id: str) -> None:
        self.collection.delete_one(
            {"inspectionId": inspection_id}
        )


inspection_repository = InspectionRepository()

def save_inspection(inspection) -> Inspection:
    if isinstance(inspection, dict):
        inspection = Inspection.model_validate(inspection)

    return inspection_repository.create(inspection)


def get_inspection(inspection_id: str):
    inspection = inspection_repository.get(inspection_id)

    if not inspection:
        return None

    return inspection.model_dump(mode="json")


def update_inspection(inspection: Inspection) -> Inspection:
    return inspection_repository.update(inspection)


def list_inspections() -> List[Inspection]:
    return inspection_repository.list_all()

def save_status(*args) -> None:
    db = get_db()
    collection = db["inspection_status"]

    if len(args) == 1:
        status = args[0]
        collection.replace_one(
            {"inspectionId": status["inspectionId"]},
            status,
            upsert=True,
        )
        return

    if len(args) == 2:
        inspection_id, status_value = args
        collection.update_one(
            {"inspectionId": inspection_id},
            {"$set": {"status": status_value}},
            upsert=True,
        )


def get_status(inspection_id: str):
    return get_db()["inspection_status"].find_one(
        {"inspectionId": inspection_id},
        {"_id": 0},
    )

def add_inspection_id(inspection_id: str) -> str:
    return inspection_id

def get_all_inspection_ids() -> List[str]:
    return [
        doc["inspectionId"]
        for doc in get_db()["inspections"].find(
            {},
            {"inspectionId": 1, "_id": 0},
        )
        if doc.get("inspectionId")
    ]