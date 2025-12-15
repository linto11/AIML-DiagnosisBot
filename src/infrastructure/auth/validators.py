"""Email and password validation functions."""
import re
from typing import Tuple


def validate_email(email: str) -> Tuple[bool, str]:
    """
    Validate email format.
    
    Args:
        email: Email address to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not email or not email.strip():
        return False, "Email is required"
    
    email = email.strip().lower()
    
    # Basic email regex pattern
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if not re.match(email_pattern, email):
        return False, "Invalid email format"
    
    # Additional checks
    if len(email) > 254:  # RFC 5321
        return False, "Email is too long"
    
    local_part, domain = email.rsplit('@', 1)
    
    if len(local_part) > 64:  # RFC 5321
        return False, "Email local part is too long"
    
    if len(domain) > 253:  # RFC 1035
        return False, "Email domain is too long"
    
    # Check for consecutive dots
    if '..' in email:
        return False, "Email cannot contain consecutive dots"
    
    # Check for dots at the beginning or end of local part
    if local_part.startswith('.') or local_part.endswith('.'):
        return False, "Email local part cannot start or end with a dot"
    
    return True, ""


def validate_password(password: str) -> Tuple[bool, str]:
    """
    Validate password strength.
    
    Password requirements:
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one number
    - At least one special character
    
    Args:
        password: Password to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not password:
        return False, "Password is required"
    
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    if len(password) > 128:  # Reasonable upper limit
        return False, "Password is too long (max 128 characters)"
    
    # Check for uppercase letter
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    
    # Check for lowercase letter
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    
    # Check for digit
    if not re.search(r'\d', password):
        return False, "Password must contain at least one number"
    
    # Check for special character
    if not re.search(r'[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\\/;\'`~]', password):
        return False, "Password must contain at least one special character"
    
    return True, ""


def validate_name(name: str, field_name: str = "Name") -> Tuple[bool, str]:
    """
    Validate name fields (firstname, lastname).
    
    Args:
        name: Name to validate
        field_name: Name of the field for error messages
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not name or not name.strip():
        return False, f"{field_name} is required"
    
    name = name.strip()
    
    if len(name) < 2:
        return False, f"{field_name} must be at least 2 characters long"
    
    if len(name) > 50:
        return False, f"{field_name} is too long (max 50 characters)"
    
    # Allow letters, spaces, hyphens, and apostrophes
    if not re.match(r"^[a-zA-Z\s\-']+$", name):
        return False, f"{field_name} can only contain letters, spaces, hyphens, and apostrophes"
    
    return True, ""


def passwords_match(password: str, confirm_password: str) -> Tuple[bool, str]:
    """
    Check if password and confirm password match.
    
    Args:
        password: Original password
        confirm_password: Confirmation password
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if password != confirm_password:
        return False, "Passwords do not match"
    
    return True, ""
