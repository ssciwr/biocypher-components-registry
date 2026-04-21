"""Transform submitted web form state into adapter generation input."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.core.dataset.document import DATASET_CONTEXT, build_creator
from src.core.shared.ids import slugify_identifier


def build_normalized_adapter_input_from_web_form(
    data: dict[str, str],
    output_dir: Path,
) -> dict[str, Any]:
    """Normalize serialized web form state into adapter config input."""
    creators = _load_creators(data)
    datasets = _load_datasets(data)

    normalized_datasets: list[dict[str, Any]] = []
    manual_datasets: list[dict[str, Any]] = []
    for dataset in datasets:
        if not isinstance(dataset, dict):
            raise ValueError("Each dataset entry must be a mapping.")
        mode = str(dataset.get("uiMode", "")).strip().lower()
        if mode == "existing" and str(dataset.get("uiExistingPath", "")).strip():
            normalized_datasets.append(
                {
                    "mode": "existing",
                    "path": str(dataset["uiExistingPath"]).strip(),
                }
            )
            continue
        if (
            mode == "generate"
            and str(dataset.get("uiInputPath", "")).strip()
            and not dataset.get("uiForceManualMetadata")
            and not _requires_manual_creator_serialization(dataset)
        ):
            normalized_datasets.append(
                {
                    "mode": "generate",
                    "input": str(dataset.get("uiInputPath", "")).strip(),
                    "name": _optional_string(dataset, "name"),
                    "description": _optional_string(dataset, "description"),
                    "license": _optional_string(dataset, "license"),
                    "url": _optional_string(dataset, "url"),
                    "dataset_version": _optional_string(dataset, "version"),
                    "date_published": _optional_string(dataset, "datePublished"),
                    "citation": _optional_string(dataset, "citeAs"),
                    "creators": [
                        item
                        for item in dataset.get("uiCreators", [])
                        if (
                            isinstance(item, dict)
                            and str(item.get("name", "")).strip()
                        )
                        or (not isinstance(item, dict) and str(item).strip())
                    ],
                }
            )
            continue
        manual_datasets.append(dataset)

    normalized_datasets.extend(
        {"mode": "existing", "path": path}
        for path in _write_manual_dataset_files(manual_datasets, output_dir)
    )

    return {
        "dataset_generator": (data.get("dataset_generator", "croissant-baker") or "croissant-baker").strip(),
        "validate": str(data.get("validate", "true")).strip().lower() == "true",
        "adapter": {
            "output": (data.get("output", "") or "").strip() or "croissant_adapter.jsonld",
            "name": data.get("name", "").strip(),
            "description": data.get("description", "").strip(),
            "version": data.get("version", "").strip(),
            "license": data.get("license", "").strip(),
            "code_repository": data.get("code_repository", "").strip(),
            "adapter_id": (data.get("adapter_id", "") or "").strip() or None,
            "keywords": [item.strip() for item in data.get("keywords", "").split(",") if item.strip()],
            "creators": creators,
        },
        "datasets": normalized_datasets,
    }


def _optional_string(mapping: dict[str, Any], key: str) -> str | None:
    """Read an optional non-empty string from a mapping."""
    value = mapping.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _load_creators(data: dict[str, str]) -> list[dict[str, Any]]:
    """Decode serialized creator state submitted by the web form."""
    raw = data.get("creators_data", "")
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid creators data: {exc}") from exc
    if not isinstance(parsed, list):
        raise ValueError("Creators data must be a list.")
    return parsed


def _load_datasets(data: dict[str, str]) -> list[dict[str, Any]]:
    """Decode serialized dataset state submitted by the web form."""
    raw = data.get("datasets_data", "")
    if not raw:
        raise ValueError("At least one dataset is required.")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid datasets data: {exc}") from exc
    if not isinstance(parsed, list) or not parsed:
        raise ValueError("Datasets data must be a non-empty list.")
    return parsed


def _slugify_id(text: str) -> str:
    """Normalize text into a stable identifier fragment."""
    return slugify_identifier(text)


def _write_manual_dataset_files(
    datasets: list[dict[str, Any]],
    output_dir: Path,
) -> list[str]:
    """Write hand-authored dataset drafts to temporary JSON-LD files."""
    if not datasets:
        return []
    temp_dir = output_dir / ".web_new_datasets"
    temp_dir.mkdir(parents=True, exist_ok=True)
    dataset_paths: list[str] = []
    for index, dataset in enumerate(datasets, start=1):
        path = temp_dir / f"dataset_{index}.jsonld"
        document = _coerce_manual_dataset(json.loads(json.dumps(dataset)))
        path.write_text(json.dumps(document, indent=2), encoding="utf-8")
        dataset_paths.append(str(path))
    return dataset_paths


def _coerce_manual_dataset(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize web-authored dataset state into a Croissant dataset document."""
    distribution = data.get("distribution")
    record_set = data.get("recordSet")
    ui_field_preview = data.get("uiFieldPreview")
    ui_draft_details = data.get("uiDraftDetails")
    if isinstance(distribution, list):
        for entry in distribution:
            if isinstance(entry, dict):
                entry.setdefault("@type", "cr:FileObject")
                if "@id" not in entry:
                    name = entry.get("name")
                    if not name and isinstance(entry.get("contentUrl"), str):
                        name = entry["contentUrl"].split("?")[0].split("/")[-1]
                    entry["@id"] = name or "file"
    if (
        isinstance(ui_field_preview, list)
        and ui_field_preview
        and (
            not isinstance(record_set, list)
            or not record_set
            or not isinstance(record_set[0], dict)
            or not isinstance(record_set[0].get("field"), list)
            or not record_set[0].get("field")
        )
    ):
        record_set_name = ""
        if isinstance(ui_draft_details, dict):
            record_set_name = str(ui_draft_details.get("recordSetName", "") or "").strip()
        if not record_set_name and isinstance(record_set, list) and record_set and isinstance(record_set[0], dict):
            record_set_name = str(record_set[0].get("name", "") or "").strip()
        if not record_set_name:
            dataset_name = str(data.get("name", "dataset") or "dataset").strip()
            record_set_name = f"{dataset_name} records" if dataset_name else "records"
        dataset_id = _slugify_id(data.get("name", "dataset") or "dataset")
        record_set_id = f"{dataset_id}-{_slugify_id(record_set_name or 'records')}"
        file_object_id = "file"
        if isinstance(distribution, list) and distribution:
            first_distribution = distribution[0]
            if isinstance(first_distribution, dict):
                file_object_id = first_distribution.get("@id", "file")
        record_set = [{
            "@type": "cr:RecordSet",
            "@id": record_set_id,
            "name": record_set_name,
            "field": [],
        }]
        for raw_field in ui_field_preview:
            if not isinstance(raw_field, dict):
                continue
            field_name = str(raw_field.get("name", "") or "").strip()
            if not field_name:
                continue
            built_field: dict[str, Any] = {
                "@type": "cr:Field",
                "@id": f"{record_set_id}/{_slugify_id(field_name)}",
                "name": field_name,
                "dataType": raw_field.get("mappedType", "sc:Text"),
                "description": str(raw_field.get("description", "") or ""),
                "source": {
                    "fileObject": {"@id": file_object_id},
                    "extract": {"column": field_name},
                },
            }
            example = raw_field.get("example")
            if example not in (None, ""):
                built_field["examples"] = [example]
            record_set[0]["field"].append(built_field)

    if isinstance(record_set, list):
        for entry in record_set:
            if isinstance(entry, dict):
                if "@type" not in entry:
                    entry["@type"] = "cr:RecordSet"
                desired_record_set_id = (
                    f"{_slugify_id(data.get('name', 'dataset') or 'dataset')}-"
                    f"{_slugify_id(entry.get('name', 'records') or 'records')}"
                )
                entry["@id"] = desired_record_set_id
                fields = entry.get("field")
                if isinstance(fields, list):
                    file_object_id = "file"
                    if isinstance(distribution, list) and distribution:
                        first = distribution[0]
                        if isinstance(first, dict):
                            file_object_id = first.get("@id", "file")
                    for field in fields:
                        if isinstance(field, dict) and "@type" not in field:
                            field["@type"] = "cr:Field"
                        if isinstance(field, dict) and "description" not in field:
                            field["description"] = ""
                        if isinstance(field, dict) and "@id" not in field:
                            record_set_id = entry.get("@id", "records")
                            field["@id"] = f"{record_set_id}/{_slugify_id(field.get('name', 'field') or 'field')}"
                        if isinstance(field, dict) and "source" not in field:
                            field["source"] = {
                                "fileObject": {"@id": file_object_id},
                                "extract": {"column": field.get("name", "")},
                            }

    creators_raw = data.get("creator", data.get("uiCreators"))
    creators: list[dict[str, Any]] = []
    if isinstance(creators_raw, list):
        for creator in creators_raw:
            if isinstance(creator, dict):
                creators.append(
                    build_creator(
                        name=str(creator.get("name", "")).strip(),
                        url=str(creator.get("url", creator.get("identifier", ""))).strip(),
                        email=str(creator.get("email", "")).strip(),
                        affiliation=str(
                            creator.get("affiliation", creator.get("affiliations", ""))
                        ).strip(),
                        creator_type=str(
                            creator.get("creator_type", creator.get("type", "Person"))
                        ).strip()
                        or "Person",
                    )
                )
            elif isinstance(creator, str) and creator.strip():
                parts = [part.strip() for part in creator.split("|")]
                if parts and parts[0].lower() in {"person", "organization"}:
                    creators.append(
                        build_creator(
                            name=parts[1] if len(parts) > 1 else "",
                            affiliation=parts[2] if len(parts) > 2 else "",
                            email=parts[3] if len(parts) > 3 else "",
                            url=parts[4] if len(parts) > 4 else "",
                            creator_type=parts[0],
                        )
                    )
                else:
                    parts = [part.strip() for part in creator.split(",")]
                    creators.append(
                        build_creator(
                            name=parts[0] if parts else "",
                            email=parts[1] if len(parts) > 1 else "",
                            url=parts[2] if len(parts) > 2 else "",
                        )
                    )

    document: dict[str, Any] = {
        "@context": DATASET_CONTEXT,
        "@type": "sc:Dataset",
        "name": data["name"],
        "description": data["description"],
        "conformsTo": "http://mlcommons.org/croissant/1.0",
        "license": data["license"],
        "url": data["url"],
        "version": data["version"],
        "distribution": distribution or [],
        "recordSet": record_set or [],
    }
    if data.get("datePublished"):
        document["datePublished"] = data["datePublished"]
    if data.get("citeAs"):
        document["citeAs"] = data["citeAs"]
    if creators:
        document["creator"] = creators[0] if len(creators) == 1 else creators
    return document


def _requires_manual_creator_serialization(dataset: dict[str, Any]) -> bool:
    """Return whether creator details require manual JSON-LD serialization."""
    creators = dataset.get("uiCreators", [])
    if not isinstance(creators, list):
        return False
    for creator in creators:
        if not isinstance(creator, dict):
            continue
        creator_type = str(
            creator.get("creator_type", creator.get("type", "Person"))
        ).strip()
        affiliations = str(
            creator.get("affiliation", creator.get("affiliations", ""))
        ).strip()
        if creator_type.lower() == "organization" or affiliations:
            return True
    return False
