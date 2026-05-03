"""CRM contact transforms for unified contact model."""

from __future__ import annotations

from typing import Any

from . import register


def _base(raw: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    """Merge overrides with raw fallback."""
    result = {
        "id": "",
        "first_name": "",
        "last_name": "",
        "email": "",
        "phone": "",
        "company": "",
        "title": "",
        "created_at": None,
        "updated_at": None,
        "raw": raw,
    }
    result.update({k: v for k, v in overrides.items() if v})
    return result


@register("salesforce", "contact")
def salesforce_contact(raw: dict[str, Any]) -> dict[str, Any]:
    return _base(
        raw,
        id=raw.get("Id", ""),
        first_name=raw.get("FirstName", ""),
        last_name=raw.get("LastName", ""),
        email=raw.get("Email", ""),
        phone=raw.get("Phone", ""),
        company=raw.get("Account", {}).get("Name", "") if isinstance(raw.get("Account"), dict) else "",
        title=raw.get("Title", ""),
        created_at=raw.get("CreatedDate"),
        updated_at=raw.get("LastModifiedDate"),
    )


@register("hubspot", "contact")
def hubspot_contact(raw: dict[str, Any]) -> dict[str, Any]:
    props = raw.get("properties", {})
    return _base(
        raw,
        id=raw.get("id", ""),
        first_name=props.get("firstname", ""),
        last_name=props.get("lastname", ""),
        email=props.get("email", ""),
        phone=props.get("phone", ""),
        company=props.get("company", ""),
        title=props.get("jobtitle", ""),
        created_at=props.get("createdate"),
        updated_at=props.get("lastmodifieddate"),
    )


@register("pipedrive", "contact")
def pipedrive_contact(raw: dict[str, Any]) -> dict[str, Any]:
    name = raw.get("name", "")
    parts = name.split(" ", 1) if name else ["", ""]
    emails = raw.get("email", [])
    phones = raw.get("phone", [])
    return _base(
        raw,
        id=str(raw.get("id", "")),
        first_name=raw.get("first_name", parts[0]),
        last_name=raw.get("last_name", parts[1] if len(parts) > 1 else ""),
        email=emails[0].get("value", "") if emails and isinstance(emails, list) else "",
        phone=phones[0].get("value", "") if phones and isinstance(phones, list) else "",
        company=raw.get("org_name", ""),
        title=raw.get("job_title", ""),
        created_at=raw.get("add_time"),
        updated_at=raw.get("update_time"),
    )


@register("zoho-crm", "contact")
def zoho_contact(raw: dict[str, Any]) -> dict[str, Any]:
    return _base(
        raw,
        id=raw.get("id", ""),
        first_name=raw.get("First_Name", ""),
        last_name=raw.get("Last_Name", ""),
        email=raw.get("Email", ""),
        phone=raw.get("Phone", ""),
        company=raw.get("Company", ""),
        title=raw.get("Title", ""),
        created_at=raw.get("Created_Time"),
        updated_at=raw.get("Modified_Time"),
    )


@register("freshsales", "contact")
def freshsales_contact(raw: dict[str, Any]) -> dict[str, Any]:
    return _base(
        raw,
        id=str(raw.get("id", "")),
        first_name=raw.get("first_name", ""),
        last_name=raw.get("last_name", ""),
        email=raw.get("email", ""),
        phone=raw.get("mobile_number", "") or raw.get("work_number", ""),
        company=raw.get("company", {}).get("name", "") if isinstance(raw.get("company"), dict) else "",
        title=raw.get("job_title", ""),
        created_at=raw.get("created_at"),
        updated_at=raw.get("updated_at"),
    )


@register("copper", "contact")
def copper_contact(raw: dict[str, Any]) -> dict[str, Any]:
    emails = raw.get("emails", [])
    phones = raw.get("phone_numbers", [])
    return _base(
        raw,
        id=str(raw.get("id", "")),
        first_name=raw.get("first_name", ""),
        last_name=raw.get("last_name", ""),
        email=emails[0].get("email", "") if emails else "",
        phone=phones[0].get("number", "") if phones else "",
        company=raw.get("company_name", ""),
        title=raw.get("title", ""),
        created_at=raw.get("date_created"),
        updated_at=raw.get("date_modified"),
    )


@register("close", "contact")
def close_contact(raw: dict[str, Any]) -> dict[str, Any]:
    emails = raw.get("emails", [])
    phones = raw.get("phones", [])
    return _base(
        raw,
        id=raw.get("id", ""),
        first_name=raw.get("first_name", ""),
        last_name=raw.get("last_name", ""),
        email=emails[0].get("email", "") if emails else "",
        phone=phones[0].get("phone", "") if phones else "",
        company=raw.get("organization_name", ""),
        title=raw.get("title", ""),
        created_at=raw.get("date_created"),
        updated_at=raw.get("date_updated"),
    )


@register("attio", "contact")
def attio_contact(raw: dict[str, Any]) -> dict[str, Any]:
    values = raw.get("values", {})

    def _first_val(field: str) -> str:
        vals = values.get(field, [])
        if vals and isinstance(vals, list):
            v = vals[0]
            if isinstance(v, dict):
                return v.get("value", v.get("original_value", ""))
            return str(v)
        return ""

    return _base(
        raw,
        id=raw.get("id", {}).get("record_id", "") if isinstance(raw.get("id"), dict) else str(raw.get("id", "")),
        first_name=_first_val("first_name"),
        last_name=_first_val("last_name"),
        email=_first_val("email_addresses"),
        phone=_first_val("phone_numbers"),
        company=_first_val("company"),
        title=_first_val("job_title"),
        created_at=raw.get("created_at"),
    )
