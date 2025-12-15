"""Unit tests for user manager."""
import pytest
import os
import json
import tempfile
from pathlib import Path
from src.infrastructure.auth.user_manager import UserManager


@pytest.fixture
def temp_storage():
    """Create a temporary storage file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


class TestUserManager:
    """Test UserManager functionality."""
    
    def test_initialization(self, temp_storage):
        """Test UserManager initializes correctly."""
        manager = UserManager(storage_path=temp_storage)
        assert os.path.exists(temp_storage)
        
        # Check that empty users dict is created
        with open(temp_storage, 'r') as f:
            users = json.load(f)
            assert users == {}
    
    def test_register_user_success(self, temp_storage):
        """Test successful user registration."""
        manager = UserManager(storage_path=temp_storage)
        
        success, message = manager.register_user(
            firstname="John",
            lastname="Doe",
            email="john.doe@example.com",
            password="Password123!"
        )
        
        assert success
        assert "successful" in message.lower()
        
        # Verify user was saved
        with open(temp_storage, 'r') as f:
            users = json.load(f)
            assert "john.doe@example.com" in users
            
            user = users["john.doe@example.com"]
            assert user["firstname"] == "John"
            assert user["lastname"] == "Doe"
            assert user["email"] == "john.doe@example.com"
            assert "password" in user
            assert user["password"] != "Password123!"  # Should be hashed
            assert "created_at" in user
            assert user["last_login"] is None
    
    def test_register_duplicate_email(self, temp_storage):
        """Test registering with duplicate email fails."""
        manager = UserManager(storage_path=temp_storage)
        
        # Register first user
        manager.register_user(
            firstname="John",
            lastname="Doe",
            email="john.doe@example.com",
            password="Password123!"
        )
        
        # Try to register with same email
        success, message = manager.register_user(
            firstname="Jane",
            lastname="Smith",
            email="john.doe@example.com",
            password="Password456!"
        )
        
        assert not success
        assert "already registered" in message.lower()
    
    def test_email_case_insensitive(self, temp_storage):
        """Test email is case-insensitive."""
        manager = UserManager(storage_path=temp_storage)
        
        # Register with lowercase
        manager.register_user(
            firstname="John",
            lastname="Doe",
            email="john.doe@example.com",
            password="Password123!"
        )
        
        # Try to register with uppercase
        success, message = manager.register_user(
            firstname="Jane",
            lastname="Smith",
            email="John.Doe@EXAMPLE.COM",
            password="Password456!"
        )
        
        assert not success
        assert "already registered" in message.lower()
    
    def test_email_exists(self, temp_storage):
        """Test email_exists method."""
        manager = UserManager(storage_path=temp_storage)
        
        # Initially should not exist
        assert not manager.email_exists("john.doe@example.com")
        
        # Register user
        manager.register_user(
            firstname="John",
            lastname="Doe",
            email="john.doe@example.com",
            password="Password123!"
        )
        
        # Now should exist
        assert manager.email_exists("john.doe@example.com")
        assert manager.email_exists("John.Doe@EXAMPLE.COM")  # Case insensitive
    
    def test_authenticate_user_success(self, temp_storage):
        """Test successful user authentication."""
        manager = UserManager(storage_path=temp_storage)
        
        # Register user
        manager.register_user(
            firstname="John",
            lastname="Doe",
            email="john.doe@example.com",
            password="Password123!"
        )
        
        # Authenticate with correct credentials
        success, user_data = manager.authenticate_user(
            email="john.doe@example.com",
            password="Password123!"
        )
        
        assert success
        assert user_data is not None
        assert user_data["firstname"] == "John"
        assert user_data["lastname"] == "Doe"
        assert user_data["email"] == "john.doe@example.com"
        assert "password" not in user_data  # Password should not be returned
    
    def test_authenticate_user_wrong_password(self, temp_storage):
        """Test authentication fails with wrong password."""
        manager = UserManager(storage_path=temp_storage)
        
        # Register user
        manager.register_user(
            firstname="John",
            lastname="Doe",
            email="john.doe@example.com",
            password="Password123!"
        )
        
        # Authenticate with wrong password
        success, user_data = manager.authenticate_user(
            email="john.doe@example.com",
            password="WrongPassword!"
        )
        
        assert not success
        assert user_data is None
    
    def test_authenticate_user_not_found(self, temp_storage):
        """Test authentication fails for non-existent user."""
        manager = UserManager(storage_path=temp_storage)
        
        # Try to authenticate non-existent user
        success, user_data = manager.authenticate_user(
            email="nonexistent@example.com",
            password="Password123!"
        )
        
        assert not success
        assert user_data is None
    
    def test_authenticate_updates_last_login(self, temp_storage):
        """Test that authentication updates last_login timestamp."""
        manager = UserManager(storage_path=temp_storage)
        
        # Register user
        manager.register_user(
            firstname="John",
            lastname="Doe",
            email="john.doe@example.com",
            password="Password123!"
        )
        
        # Authenticate
        manager.authenticate_user(
            email="john.doe@example.com",
            password="Password123!"
        )
        
        # Check last_login was updated
        with open(temp_storage, 'r') as f:
            users = json.load(f)
            user = users["john.doe@example.com"]
            assert user["last_login"] is not None
    
    def test_get_user(self, temp_storage):
        """Test get_user method."""
        manager = UserManager(storage_path=temp_storage)
        
        # Register user
        manager.register_user(
            firstname="John",
            lastname="Doe",
            email="john.doe@example.com",
            password="Password123!"
        )
        
        # Get user
        user_data = manager.get_user("john.doe@example.com")
        
        assert user_data is not None
        assert user_data["firstname"] == "John"
        assert user_data["lastname"] == "Doe"
        assert user_data["email"] == "john.doe@example.com"
        assert "password" not in user_data
        
        # Get non-existent user
        user_data = manager.get_user("nonexistent@example.com")
        assert user_data is None
    
    def test_password_hashing(self, temp_storage):
        """Test that passwords are properly hashed."""
        manager = UserManager(storage_path=temp_storage)
        
        password = "Password123!"
        
        # Register user
        manager.register_user(
            firstname="John",
            lastname="Doe",
            email="john.doe@example.com",
            password=password
        )
        
        # Load user and check password is hashed
        with open(temp_storage, 'r') as f:
            users = json.load(f)
            stored_password = users["john.doe@example.com"]["password"]
            
            # Password should not be stored in plain text
            assert stored_password != password
            
            # Password should be bcrypt hash (starts with $2b$)
            assert stored_password.startswith("$2b$")
    
    def test_whitespace_trimming(self, temp_storage):
        """Test that whitespace is trimmed from inputs."""
        manager = UserManager(storage_path=temp_storage)
        
        # Register with extra whitespace
        manager.register_user(
            firstname="  John  ",
            lastname="  Doe  ",
            email="  john.doe@example.com  ",
            password="Password123!"
        )
        
        # Verify whitespace was trimmed
        user_data = manager.get_user("john.doe@example.com")
        assert user_data["firstname"] == "John"
        assert user_data["lastname"] == "Doe"
        assert user_data["email"] == "john.doe@example.com"
    
    def test_multiple_users(self, temp_storage):
        """Test registering and authenticating multiple users."""
        manager = UserManager(storage_path=temp_storage)
        
        # Register multiple users
        users_to_register = [
            ("John", "Doe", "john@example.com", "Password1!"),
            ("Jane", "Smith", "jane@example.com", "Password2!"),
            ("Bob", "Johnson", "bob@example.com", "Password3!"),
        ]
        
        for firstname, lastname, email, password in users_to_register:
            success, _ = manager.register_user(firstname, lastname, email, password)
            assert success
        
        # Authenticate each user
        for firstname, lastname, email, password in users_to_register:
            success, user_data = manager.authenticate_user(email, password)
            assert success
            assert user_data["firstname"] == firstname
            assert user_data["email"] == email
