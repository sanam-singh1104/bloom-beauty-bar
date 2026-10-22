"""Turn validation failures into one clear, customer-facing error shape.

Every 422 looks like {"detail": "<one line for people>", "errors": [...]},
where each error is {"field", "message", "missing": bool}.
"""

from fastapi.responses import JSONResponse

# Customer-facing names for request fields, used in error messages.
FIELD_LABELS = {
    "service_id": "service",
    "starts_at": "date and time",
    "customer_name": "name",
    "customer_contact": "contact",
}


def field_error(field: str, message: str, missing: bool = False) -> dict:
    return {"field": field, "message": message, "missing": missing}


def describe_errors(pydantic_errors: list[dict]) -> list[dict]:
    """Map pydantic/FastAPI validation errors to field errors.

    Absent, null, and blank values all count as missing.
    """
    errors = []
    for err in pydantic_errors:
        if err["type"] == "json_invalid" or tuple(err["loc"]) == ("body",):
            errors.append(field_error("body", "Request body must be a JSON object"))
            continue
        field = str(err["loc"][-1])
        label = FIELD_LABELS.get(field, field)
        value = err.get("input")
        is_missing = (
            err["type"] == "missing"
            or value is None
            or (isinstance(value, str) and not value.strip())
        )
        if is_missing:
            message = "Field required"
        elif err["type"] == "value_error":
            message = err["msg"].removeprefix("Value error, ")
        else:
            message = f"Invalid {label}: {err['msg']}"
        errors.append(field_error(field, message, is_missing))
    return errors


def summarize(errors: list[dict]) -> str:
    """One line for people, e.g. "Please provide: name, contact."."""
    missing = [FIELD_LABELS.get(e["field"], e["field"]) for e in errors if e["missing"]]
    parts = []
    if missing:
        parts.append(f"Please provide: {', '.join(missing)}.")
    parts += [e["message"] + "." for e in errors if not e["missing"]]
    return " ".join(parts)


def validation_error(errors: list[dict]) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": summarize(errors), "errors": errors},
    )
