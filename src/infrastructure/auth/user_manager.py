"""User management with secure password hashing and storage."""
import json
import os
import time
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from datetime import datetime
import bcrypt


class UserManager:
    """Manages user registration, authentication, and storage."""
    
    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize UserManager.
        
        Args:
            storage_path: Path to JSON file for user storage. 
                         Defaults to .streamlit/users.json
        """
        if storage_path is None:
            # Store in .streamlit directory (which is in .gitignore)
            # Navigate from this file to project root, then to .streamlit/users.json
            project_root = Path(__file__).parent.parent.parent.parent
            storage_path = str(project_root / ".streamlit" / "users.json")
        
        self.storage_path = storage_path
        self._ensure_storage_exists()
    
    def _ensure_storage_exists(self) -> None:
        """Create storage directory and file if they don't exist."""
        storage_dir = os.path.dirname(self.storage_path)
        if storage_dir and not os.path.exists(storage_dir):
            os.makedirs(storage_dir, exist_ok=True)
        
        if not os.path.exists(self.storage_path):
            self._save_users({})
        elif os.path.getsize(self.storage_path) == 0:
            # If file exists but is empty, initialize it
            self._save_users({})
    
    def _load_users(self) -> Dict[str, Any]:
        """Load users from storage file."""
        try:
            with open(self.storage_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def _save_users(self, users: Dict[str, Any]) -> None:
        """Save users to storage file."""
        with open(self.storage_path, 'w') as f:
            json.dump(users, f, indent=2)
    
    def _hash_password(self, password: str) -> str:
        """
        Hash password using bcrypt.
        
        Args:
            password: Plain text password
            
        Returns:
            Hashed password as string
        """
        # Generate salt and hash password
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    def _verify_password(self, password: str, hashed_password: str) -> bool:
        """
        Verify password against hashed password.
        
        Args:
            password: Plain text password to verify
            hashed_password: Hashed password to compare against
            
        Returns:
            True if password matches, False otherwise
        """
        try:
            return bcrypt.checkpw(
                password.encode('utf-8'),
                hashed_password.encode('utf-8')
            )
        except Exception:
            return False
    
    def email_exists(self, email: str) -> bool:
        """
        Check if email already exists in the system.
        
        Args:
            email: Email to check
            
        Returns:
            True if email exists, False otherwise
        """
        users = self._load_users()
        email = email.strip().lower()
        return email in users
    
    def register_user(
        self,
        firstname: str,
        lastname: str,
        email: str,
        password: str
    ) -> Tuple[bool, str]:
        """
        Register a new user.
        
        Args:
            firstname: User's first name
            lastname: User's last name
            email: User's email address
            password: User's plain text password (will be hashed)
            
        Returns:
            Tuple of (success, message)
        """
        email = email.strip().lower()
        
        # Check if email already exists
        if self.email_exists(email):
            return False, "Email already registered"
        
        # Hash password
        hashed_password = self._hash_password(password)
        
        # Load existing users
        users = self._load_users()
        
        # Create user record
        users[email] = {
            "firstname": firstname.strip(),
            "lastname": lastname.strip(),
            "email": email,
            "password": hashed_password,
            "created_at": datetime.now().isoformat(),
            "last_login": None
        }
        
        # Save users
        try:
            self._save_users(users)
            return True, "Registration successful"
        except Exception as e:
            return False, f"Failed to save user: {str(e)}"
    
    def authenticate_user(self, email: str, password: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Authenticate user with email and password.
        
        Args:
            email: User's email address
            password: User's plain text password
            
        Returns:
            Tuple of (success, user_data or None)
            user_data contains: firstname, lastname, email (without password)
        """
        email = email.strip().lower()
        users = self._load_users()
        
        # Check if user exists
        if email not in users:
            return False, None
        
        user = users[email]
        
        # Verify password
        if not self._verify_password(password, user["password"]):
            return False, None
        
        # Update last login
        user["last_login"] = datetime.now().isoformat()
        self._save_users(users)
        
        # Return user data without password
        user_data = {
            "firstname": user["firstname"],
            "lastname": user["lastname"],
            "email": user["email"]
        }
        
        return True, user_data
    
    def get_user(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Get user data by email.
        
        Args:
            email: User's email address
            
        Returns:
            User data without password, or None if not found
        """
        email = email.strip().lower()
        users = self._load_users()
        
        if email not in users:
            return None
        
        user = users[email]
        return {
            "firstname": user["firstname"],
            "lastname": user["lastname"],
            "email": user["email"]
        }
