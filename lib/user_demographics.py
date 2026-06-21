from __future__ import annotations

SEX_OPTIONS = ["Male", "Female"]
MIN_AGE = 1
MAX_AGE = 120


def is_valid_sex(sex: str | None) -> bool:
    return sex in SEX_OPTIONS


def normalize_age(age: int | float | str | None) -> int | None:
    if age is None or age == "":
        return None
    try:
        value = int(age)
    except (TypeError, ValueError):
        return None
    if MIN_AGE <= value <= MAX_AGE:
        return value
    return None


def sex_age_validation_errors(sex: str | None, age: int | float | str | None) -> list[str]:
    errors: list[str] = []
    if not is_valid_sex(sex):
        errors.append("Please select sex (Male or Female).")
    if normalize_age(age) is None:
        errors.append(f"Please enter a valid age ({MIN_AGE}-{MAX_AGE}).")
    return errors
