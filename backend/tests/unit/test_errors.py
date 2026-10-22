"""Turning validation failures into customer-facing messages."""

import json

from app.errors import describe_errors, field_error, summarize, validation_error


def test_absent_null_and_blank_all_count_as_missing():
    errors = describe_errors(
        [
            {
                "type": "missing",
                "loc": ("body", "service_id"),
                "msg": "Field required",
                "input": {},
            },
            {"type": "string_type", "loc": ("body", "customer_name"), "msg": "...", "input": None},
            {"type": "datetime_parsing", "loc": ("body", "starts_at"), "msg": "...", "input": "  "},
        ]
    )
    assert errors == [
        field_error("service_id", "Field required", missing=True),
        field_error("customer_name", "Field required", missing=True),
        field_error("starts_at", "Field required", missing=True),
    ]


def test_value_error_keeps_our_message_without_prefix():
    [error] = describe_errors(
        [
            {
                "type": "value_error",
                "loc": ("body", "customer_contact"),
                "msg": "Value error, Enter a valid phone number or email address",
                "input": "call me",
            }
        ]
    )
    assert error == field_error("customer_contact", "Enter a valid phone number or email address")


def test_type_error_names_the_field_in_plain_words():
    [error] = describe_errors(
        [
            {
                "type": "datetime_from_date_parsing",
                "loc": ("body", "starts_at"),
                "msg": "Input should be a valid datetime",
                "input": "next tuesday",
            }
        ]
    )
    assert error["message"] == "Invalid date and time: Input should be a valid datetime"
    assert error["missing"] is False


def test_bad_json_body():
    [error] = describe_errors(
        [{"type": "json_invalid", "loc": ("body", 0), "msg": "JSON decode error", "input": {}}]
    )
    assert error == field_error("body", "Request body must be a JSON object")


def test_summary_lists_missing_fields_then_other_problems():
    summary = summarize(
        [
            field_error("starts_at", "Field required", missing=True),
            field_error("customer_contact", "Enter a valid phone number or email address"),
            field_error("customer_name", "Field required", missing=True),
        ]
    )
    assert summary == (
        "Please provide: date and time, name. Enter a valid phone number or email address."
    )


def test_validation_error_response_shape():
    errors = [field_error("service_id", "The selected service doesn't exist")]
    response = validation_error(errors)
    assert response.status_code == 422
    assert json.loads(response.body) == {
        "detail": "The selected service doesn't exist.",
        "errors": errors,
    }
