"""UK-first phone number normalisation to E.164."""

import phonenumbers


def to_e164(number, region="GB"):
    """Return `number` in E.164 (e.g. +447700900123), or False when it is not a valid number."""
    if not number:
        return False
    try:
        parsed = phonenumbers.parse(str(number), region)
    except phonenumbers.NumberParseException:
        return False
    if not phonenumbers.is_possible_number(parsed):
        return False
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
