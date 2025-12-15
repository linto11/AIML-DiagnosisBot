"""Authentication screens for login and registration."""
import time
import streamlit as st
from src.infrastructure.auth.validators import (
    validate_email,
    validate_password,
    validate_name,
    passwords_match
)
from src.infrastructure.auth.user_manager import UserManager


def show_login_screen() -> bool:
    """
    Display login screen.
    
    Returns:
        True if user successfully logged in, False otherwise
    """
    st.markdown("# 🔐 Login")
    st.markdown("Please enter your credentials to access the Virtual Health Assistant.")
    
    with st.form("login_form"):
        email = st.text_input("Email", placeholder="your.email@example.com")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        
        col1, col2 = st.columns([1, 1])
        with col1:
            submit = st.form_submit_button("Login", use_container_width=True)
        with col2:
            register_btn = st.form_submit_button("Need an account? Register", use_container_width=True)
        
        if register_btn:
            st.session_state.auth_mode = "register"
            st.rerun()
        
        if submit:
            # Validate inputs
            if not email or not password:
                st.error("❌ Please enter both email and password")
                return False
            
            # Validate email format
            email_valid, email_error = validate_email(email)
            if not email_valid:
                st.error(f"❌ {email_error}")
                return False
            
            # Attempt authentication
            user_manager = UserManager()
            success, user_data = user_manager.authenticate_user(email, password)
            
            if success:
                # Store user data in session state
                st.session_state.authenticated = True
                st.session_state.user_data = user_data
                st.success(f"✅ Welcome back, {user_data['firstname']}!")
                st.rerun()
                return True
            else:
                st.error("❌ Invalid email or password")
                return False
    
    return False


def show_register_screen() -> bool:
    """
    Display registration screen.
    
    Returns:
        True if user successfully registered, False otherwise
    """
    st.markdown("# ✍️ Register")
    st.markdown("Create a new account to access the Virtual Health Assistant.")
    
    with st.form("register_form"):
        firstname = st.text_input("First Name", placeholder="John")
        lastname = st.text_input("Last Name", placeholder="Doe")
        email = st.text_input("Email", placeholder="your.email@example.com")
        password = st.text_input("Password", type="password", placeholder="Enter a strong password")
        confirm_password = st.text_input("Confirm Password", type="password", placeholder="Re-enter your password")
        
        st.caption("Password must be at least 8 characters and include uppercase, lowercase, number, and special character.")
        
        col1, col2 = st.columns([1, 1])
        with col1:
            submit = st.form_submit_button("Register", use_container_width=True)
        with col2:
            login_btn = st.form_submit_button("Already have an account? Login", use_container_width=True)
        
        if login_btn:
            st.session_state.auth_mode = "login"
            st.rerun()
        
        if submit:
            # Validate all inputs
            errors = []
            
            # Validate first name
            firstname_valid, firstname_error = validate_name(firstname, "First name")
            if not firstname_valid:
                errors.append(firstname_error)
            
            # Validate last name
            lastname_valid, lastname_error = validate_name(lastname, "Last name")
            if not lastname_valid:
                errors.append(lastname_error)
            
            # Validate email
            email_valid, email_error = validate_email(email)
            if not email_valid:
                errors.append(email_error)
            
            # Validate password
            password_valid, password_error = validate_password(password)
            if not password_valid:
                errors.append(password_error)
            
            # Check passwords match
            if password_valid:  # Only check if password is valid
                match_valid, match_error = passwords_match(password, confirm_password)
                if not match_valid:
                    errors.append(match_error)
            
            # Display errors if any
            if errors:
                for error in errors:
                    st.error(f"❌ {error}")
                return False
            
            # Attempt registration
            user_manager = UserManager()
            success, message = user_manager.register_user(
                firstname=firstname,
                lastname=lastname,
                email=email,
                password=password
            )
            
            if success:
                st.success(f"✅ {message}! Please login to continue.")
                st.info("Redirecting to login page in 2 seconds...")
                # Switch to login mode
                st.session_state.auth_mode = "login"
                time.sleep(2)
                st.rerun()
                return True
            else:
                st.error(f"❌ {message}")
                return False
    
    return False


def show_auth_screen() -> bool:
    """
    Display appropriate authentication screen based on session state.
    
    Returns:
        True if user is authenticated, False otherwise
    """
    # Initialize auth mode if not set
    if "auth_mode" not in st.session_state:
        st.session_state.auth_mode = "login"
    
    # Check if user is already authenticated
    if st.session_state.get("authenticated", False):
        return True
    
    # Show appropriate screen
    if st.session_state.auth_mode == "register":
        return show_register_screen()
    else:
        return show_login_screen()


def logout():
    """Logout current user."""
    st.session_state.authenticated = False
    st.session_state.user_data = None
    st.session_state.auth_mode = "login"
    # Clear other session state
    if "smart_conversation" in st.session_state:
        del st.session_state.smart_conversation
    if "chat_messages" in st.session_state:
        del st.session_state.chat_messages
    if "assessment_result" in st.session_state:
        del st.session_state.assessment_result
    if "doctors" in st.session_state:
        del st.session_state.doctors
    st.rerun()
