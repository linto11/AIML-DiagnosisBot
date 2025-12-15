"""Unit tests for authentication validators."""
import pytest
from src.infrastructure.auth.validators import (
    validate_email,
    validate_password,
    validate_name,
    passwords_match
)


class TestValidateEmail:
    """Test email validation."""
    
    def test_valid_emails(self):
        """Test valid email formats."""
        valid_emails = [
            "user@example.com",
            "test.user@example.com",
            "test+user@example.co.uk",
            "user123@test-domain.com",
            "a@b.co",
            "test_user@example.com",
        ]
        
        for email in valid_emails:
            is_valid, error = validate_email(email)
            assert is_valid, f"Email '{email}' should be valid but got error: {error}"
            assert error == ""
    
    def test_invalid_email_format(self):
        """Test invalid email formats."""
        invalid_emails = [
            "notanemail",
            "@example.com",
            "user@",
            "user@.com",
            "user..name@example.com",
            ".user@example.com",
            "user.@example.com",
            "user@example",
            "user name@example.com",
        ]
        
        for email in invalid_emails:
            is_valid, error = validate_email(email)
            assert not is_valid, f"Email '{email}' should be invalid"
            assert error != ""
    
    def test_empty_email(self):
        """Test empty or whitespace email."""
        is_valid, error = validate_email("")
        assert not is_valid
        assert error == "Email is required"
        
        is_valid, error = validate_email("   ")
        assert not is_valid
        assert error == "Email is required"
    
    def test_email_too_long(self):
        """Test email length limits."""
        # Email longer than 254 characters
        long_email = "a" * 240 + "@example.com"
        is_valid, error = validate_email(long_email)
        assert not is_valid
        assert "too long" in error.lower()
    
    def test_local_part_too_long(self):
        """Test local part length limit (64 characters)."""
        long_local = "a" * 65 + "@example.com"
        is_valid, error = validate_email(long_local)
        assert not is_valid
        assert "local part" in error.lower()
    
    def test_case_insensitive(self):
        """Test that email validation handles case properly."""
        is_valid, error = validate_email("User@Example.COM")
        assert is_valid
        assert error == ""


class TestValidatePassword:
    """Test password validation."""
    
    def test_valid_passwords(self):
        """Test valid password formats."""
        valid_passwords = [
            "Password1!",
            "Abcd1234!",
            "MyP@ssw0rd",
            "Str0ng!Pass",
            "C0mpl3x#Pass",
        ]
        
        for password in valid_passwords:
            is_valid, error = validate_password(password)
            assert is_valid, f"Password '{password}' should be valid but got error: {error}"
            assert error == ""
    
    def test_password_too_short(self):
        """Test password minimum length."""
        is_valid, error = validate_password("Pass1!")
        assert not is_valid
        assert "at least 8 characters" in error
    
    def test_password_missing_uppercase(self):
        """Test password requires uppercase letter."""
        is_valid, error = validate_password("password1!")
        assert not is_valid
        assert "uppercase" in error.lower()
    
    def test_password_missing_lowercase(self):
        """Test password requires lowercase letter."""
        is_valid, error = validate_password("PASSWORD1!")
        assert not is_valid
        assert "lowercase" in error.lower()
    
    def test_password_missing_digit(self):
        """Test password requires digit."""
        is_valid, error = validate_password("Password!")
        assert not is_valid
        assert "number" in error.lower()
    
    def test_password_missing_special_char(self):
        """Test password requires special character."""
        is_valid, error = validate_password("Password1")
        assert not is_valid
        assert "special character" in error.lower()
    
    def test_empty_password(self):
        """Test empty password."""
        is_valid, error = validate_password("")
        assert not is_valid
        assert error == "Password is required"
    
    def test_password_too_long(self):
        """Test password maximum length."""
        long_password = "P@ssw0rd" + "a" * 130
        is_valid, error = validate_password(long_password)
        assert not is_valid
        assert "too long" in error.lower()


class TestValidateName:
    """Test name validation."""
    
    def test_valid_names(self):
        """Test valid name formats."""
        valid_names = [
            "John",
            "Mary-Jane",
            "O'Brien",
            "Jean Paul",
            "Anne Marie",
        ]
        
        for name in valid_names:
            is_valid, error = validate_name(name, "Name")
            assert is_valid, f"Name '{name}' should be valid but got error: {error}"
            assert error == ""
    
    def test_name_too_short(self):
        """Test name minimum length."""
        is_valid, error = validate_name("A", "Name")
        assert not is_valid
        assert "at least 2 characters" in error
    
    def test_name_too_long(self):
        """Test name maximum length."""
        long_name = "A" * 51
        is_valid, error = validate_name(long_name, "Name")
        assert not is_valid
        assert "too long" in error.lower()
    
    def test_empty_name(self):
        """Test empty or whitespace name."""
        is_valid, error = validate_name("", "Name")
        assert not is_valid
        assert error == "Name is required"
        
        is_valid, error = validate_name("   ", "Name")
        assert not is_valid
        assert error == "Name is required"
    
    def test_name_invalid_characters(self):
        """Test name with invalid characters."""
        invalid_names = [
            "John123",
            "Mary@Jane",
            "Test#Name",
            "Name_Test",
        ]
        
        for name in invalid_names:
            is_valid, error = validate_name(name, "Name")
            assert not is_valid, f"Name '{name}' should be invalid"
            assert "can only contain" in error
    
    def test_custom_field_name(self):
        """Test custom field name in error messages."""
        is_valid, error = validate_name("", "First name")
        assert not is_valid
        assert "First name is required" == error
        
        is_valid, error = validate_name("A", "Last name")
        assert not is_valid
        assert "Last name" in error


class TestPasswordsMatch:
    """Test password matching validation."""
    
    def test_matching_passwords(self):
        """Test passwords that match."""
        is_valid, error = passwords_match("Password1!", "Password1!")
        assert is_valid
        assert error == ""
    
    def test_non_matching_passwords(self):
        """Test passwords that don't match."""
        is_valid, error = passwords_match("Password1!", "Password2!")
        assert not is_valid
        assert error == "Passwords do not match"
    
    def test_case_sensitive_matching(self):
        """Test password matching is case-sensitive."""
        is_valid, error = passwords_match("Password1!", "password1!")
        assert not is_valid
        assert error == "Passwords do not match"
    
    def test_empty_passwords(self):
        """Test matching with empty passwords."""
        is_valid, error = passwords_match("", "")
        assert is_valid  # Empty strings match
        assert error == ""
