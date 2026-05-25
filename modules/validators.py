
from pydantic import BaseModel, EmailStr, field_validator, ValidationError
import re


# ── Registration Validator ──────────────────────────────────────────────────
# This checks data from the register form

class RegisterSchema(BaseModel):
    name: str
    email: EmailStr          # Pydantic checks email format automatically
    password: str
    phone: str = ''          # Optional — empty string by default

    @field_validator('name')
    @classmethod
    def name_not_empty(cls, v):
        if not v.strip():
            raise ValueError('Name cannot be empty.')
        if len(v.strip()) < 2:
            raise ValueError('Name must be at least 2 characters.')
        return v.strip()

    @field_validator('password')
    @classmethod
    def password_length(cls, v):
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters.')
        return v

    @field_validator('phone')
    @classmethod
    def phone_format(cls, v):
        # Allow empty phone (it's optional)
        if not v or not v.strip():
            return v
        # Philippine mobile: 09XXXXXXXXX (11 digits) or +639XXXXXXXXX
        pattern = r'^(09\d{9}|\+639\d{9})$'
        if not re.match(pattern, v.strip()):
            raise ValueError('Phone must be a valid PH number (e.g. 09XXXXXXXXX or +639XXXXXXXXX).')
        return v.strip()


# ── Booking Validator ───────────────────────────────────────────────────────
# This checks data from the booking form

class BookingSchema(BaseModel):
    phone: str = ''
    social: str = ''

    @field_validator('phone')
    @classmethod
    def phone_format(cls, v):
        if not v or not v.strip():
            return v
        pattern = r'^(09\d{9}|\+639\d{9})$'
        if not re.match(pattern, v.strip()):
            raise ValueError('Phone must be a valid PH number (e.g. 09XXXXXXXXX or +639XXXXXXXXX).')
        return v.strip()


# ── Helper function ─────────────────────────────────────────────────────────
# Call this to validate data and get back a clean list of error messages

def validate(schema_class, data: dict):
    """
    Returns (validated_data, errors)
    - validated_data: the cleaned data if valid, None if not
    - errors: list of error messages, empty if valid

    Usage:
        data, errors = validate(RegisterSchema, {'name': ..., 'email': ..., ...})
        if errors:
            for e in errors:
                flash(e, 'error')
            return redirect(...)
    """
    try:
        validated = schema_class(**data)
        return validated, []
    except ValidationError as e:
        errors = []
        for err in e.errors():
            loc = str(err.get('loc', ''))
            if 'email' in loc:
                errors.append('Please enter a valid email address.')
            else:
                errors.append(err['msg'].replace('Value error, ', ''))
        return None, errors
