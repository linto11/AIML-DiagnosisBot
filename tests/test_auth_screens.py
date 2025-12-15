"""Integration tests for authentication screens."""
import pytest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from src.infrastructure.auth.user_manager import UserManager


class MockSessionState(dict):
    """Mock Streamlit session state."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__dict__ = self


@pytest.fixture
def temp_storage():
    """Create a temporary storage file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def mock_streamlit():
    """Mock streamlit module."""
    with patch('src.presentation.auth_screens.st') as mock_st:
        mock_st.session_state = MockSessionState()
        yield mock_st


class TestAuthScreensIntegration:
    """Integration tests for auth screens."""
    
    def test_user_registration_and_login_flow(self, temp_storage):
        """Test complete registration and login flow."""
        manager = UserManager(storage_path=temp_storage)
        
        # Step 1: Register a new user
        success, message = manager.register_user(
            firstname="John",
            lastname="Doe",
            email="john.doe@example.com",
            password="Password123!"
        )
        
        assert success
        assert "successful" in message.lower()
        
        # Step 2: Verify user cannot register with same email
        success, message = manager.register_user(
            firstname="Jane",
            lastname="Smith",
            email="john.doe@example.com",
            password="Password456!"
        )
        
        assert not success
        assert "already registered" in message.lower()
        
        # Step 3: Login with correct credentials
        success, user_data = manager.authenticate_user(
            email="john.doe@example.com",
            password="Password123!"
        )
        
        assert success
        assert user_data["firstname"] == "John"
        assert user_data["lastname"] == "Doe"
        assert user_data["email"] == "john.doe@example.com"
        
        # Step 4: Login with wrong password fails
        success, user_data = manager.authenticate_user(
            email="john.doe@example.com",
            password="WrongPassword!"
        )
        
        assert not success
        assert user_data is None
    
    def test_logout_functionality(self, mock_streamlit):
        """Test logout clears session state."""
        from src.presentation.auth_screens import logout
        
        # Set up authenticated session
        mock_streamlit.session_state.update({
            'authenticated': True,
            'user_data': {'firstname': 'John', 'email': 'john@example.com'},
            'auth_mode': 'login',
            'smart_conversation': Mock(),
            'chat_messages': ['message1', 'message2'],
            'assessment_result': {'some': 'data'},
            'doctors': ['doc1', 'doc2']
        })
        
        # Mock st.rerun to avoid actual rerun
        mock_streamlit.rerun = Mock(side_effect=Exception("rerun called"))
        
        # Call logout
        with pytest.raises(Exception, match="rerun called"):
            logout()
        
        # Verify session state was cleared
        assert not mock_streamlit.session_state.get('authenticated', False)
        assert mock_streamlit.session_state.get('user_data') is None
        assert mock_streamlit.session_state.get('auth_mode') == 'login'
        assert 'smart_conversation' not in mock_streamlit.session_state
        assert 'chat_messages' not in mock_streamlit.session_state
        assert 'assessment_result' not in mock_streamlit.session_state
        assert 'doctors' not in mock_streamlit.session_state
    
    def test_validation_in_registration_flow(self, temp_storage):
        """Test that validation works correctly in registration."""
        from src.infrastructure.auth.validators import (
            validate_email,
            validate_password,
            validate_name,
            passwords_match
        )
        
        # Test invalid email
        is_valid, error = validate_email("invalid-email")
        assert not is_valid
        assert error != ""
        
        # Test weak password
        is_valid, error = validate_password("weak")
        assert not is_valid
        assert "at least 8 characters" in error
        
        # Test invalid name
        is_valid, error = validate_name("X", "First name")
        assert not is_valid
        assert "at least 2 characters" in error
        
        # Test password mismatch
        is_valid, error = passwords_match("Password1!", "Password2!")
        assert not is_valid
        assert "do not match" in error
        
        # Test all valid inputs
        manager = UserManager(storage_path=temp_storage)
        
        # Validate inputs before registration
        email_valid, _ = validate_email("john@example.com")
        password_valid, _ = validate_password("Password123!")
        firstname_valid, _ = validate_name("John", "First name")
        lastname_valid, _ = validate_name("Doe", "Last name")
        match_valid, _ = passwords_match("Password123!", "Password123!")
        
        assert all([email_valid, password_valid, firstname_valid, lastname_valid, match_valid])
        
        # Register should succeed
        success, message = manager.register_user(
            firstname="John",
            lastname="Doe",
            email="john@example.com",
            password="Password123!"
        )
        
        assert success
    
    def test_case_insensitive_login(self, temp_storage):
        """Test login is case-insensitive for email."""
        manager = UserManager(storage_path=temp_storage)
        
        # Register with lowercase email
        manager.register_user(
            firstname="John",
            lastname="Doe",
            email="john.doe@example.com",
            password="Password123!"
        )
        
        # Login with uppercase email
        success, user_data = manager.authenticate_user(
            email="John.Doe@EXAMPLE.COM",
            password="Password123!"
        )
        
        assert success
        assert user_data is not None
        assert user_data["email"] == "john.doe@example.com"  # Stored in lowercase
    
    def test_session_state_management(self, mock_streamlit):
        """Test session state initialization and management."""
        from src.presentation.auth_screens import show_auth_screen
        
        # Initially, auth_mode should not be set
        assert 'auth_mode' not in mock_streamlit.session_state
        
        # Mock form submission to prevent actual rendering
        with patch('src.presentation.auth_screens.show_login_screen', return_value=False):
            show_auth_screen()
        
        # After calling show_auth_screen, auth_mode should be set to login
        assert mock_streamlit.session_state.get('auth_mode') == 'login'
    
    def test_authenticated_user_bypass(self, mock_streamlit):
        """Test that authenticated users bypass auth screens."""
        from src.presentation.auth_screens import show_auth_screen
        
        # Set user as authenticated
        mock_streamlit.session_state['authenticated'] = True
        
        # Should return True immediately without showing forms
        result = show_auth_screen()
        
        assert result is True
    
    def test_password_not_stored_in_plain_text(self, temp_storage):
        """Test that passwords are never stored in plain text."""
        manager = UserManager(storage_path=temp_storage)
        
        password = "MySecretPassword123!"
        
        manager.register_user(
            firstname="John",
            lastname="Doe",
            email="john@example.com",
            password=password
        )
        
        # Read the storage file directly
        import json
        with open(temp_storage, 'r') as f:
            data = json.load(f)
        
        stored_password = data['john@example.com']['password']
        
        # Password should not match plain text
        assert stored_password != password
        
        # Should be a bcrypt hash
        assert stored_password.startswith('$2b$')
        assert len(stored_password) == 60  # bcrypt hashes are 60 characters
    
    def test_multiple_registration_attempts(self, temp_storage):
        """Test handling multiple registration attempts."""
        manager = UserManager(storage_path=temp_storage)
        
        # First registration
        success1, msg1 = manager.register_user(
            firstname="John",
            lastname="Doe",
            email="john@example.com",
            password="Password123!"
        )
        assert success1
        
        # Second attempt with same email
        success2, msg2 = manager.register_user(
            firstname="John",
            lastname="Doe",
            email="john@example.com",
            password="Password123!"
        )
        assert not success2
        assert "already registered" in msg2.lower()
        
        # Third attempt with different case
        success3, msg3 = manager.register_user(
            firstname="John",
            lastname="Doe",
            email="JOHN@EXAMPLE.COM",
            password="Password123!"
        )
        assert not success3
        assert "already registered" in msg3.lower()
