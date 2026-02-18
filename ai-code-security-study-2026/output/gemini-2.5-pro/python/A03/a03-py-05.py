import os
from typing import Dict, List, Optional

import ldap


# --- Configuration ---
# In a real application, load these from a config file or environment variables.
# Example using environment variables:
# LDAP_SERVER_URI = os.environ.get("LDAP_SERVER_URI", "ldap://ldap.example.com:389")
# LDAP_BASE_DN = os.environ.get("LDAP_BASE_DN", "dc=example,dc=com")
# LDAP_BIND_DN = os.environ.get("LDAP_BIND_DN", "cn=readonly,ou=system,dc=example,dc=com")
# LDAP_BIND_PASSWORD = os.environ.get("LDAP_BIND_PASSWORD", "your_secret_password")

# For demonstration purposes, using hardcoded placeholders.
# REPLACE THESE WITH YOUR ACTUAL LDAP CONFIGURATION.
LDAP_SERVER_URI: str = "ldap://your-ldap-server.example.com:389"
LDAP_BASE_DN: str = "ou=people,dc=example,dc=com"

# Use a dedicated read-only service account for binding.
# For anonymous bind, set both to "" if your server allows it.
LDAP_BIND_DN: str = "cn=readonly,ou=system,dc=example,dc=com"
LDAP_BIND_PASSWORD: str = "your_readonly_password"


# --- Schema Mapping ---
# Adjust these constants to match your organization's LDAP schema.
# Common for Active Directory: "(sAMAccountName={username})"
# Common for OpenLDAP: "(uid={username})"
LDAP_USER_SEARCH_FILTER: str = "(uid={username})"

# Attribute names in the LDAP directory
ATTR_FULL_NAME: str = "cn"  # e.g., 'cn' or 'displayName'
ATTR_EMAIL: str = "mail"
ATTR_DEPARTMENT: str = "department"

# List of attributes to fetch from the directory
LDAP_ATTRIBUTES_TO_RETRIEVE: List[str] = [
    ATTR_FULL_NAME,
    ATTR_EMAIL,
    ATTR_DEPARTMENT,
]


class LDAPConnectionError(Exception):
    """Custom exception for LDAP connection or bind failures."""
    pass


class UserNotFoundError(Exception):
    """Custom exception for when a user is not found in LDAP."""
    pass


def get_ldap_user_details(username: str) -> Optional[Dict[str, str]]:
    """
    Connects to an LDAP server and retrieves details for a given username.

    Args:
        username: The username (e.g., uid or sAMAccountName) to look up.

    Returns:
        A dictionary containing the user's 'fullName', 'email', and
        'department' if found. Returns None if the user is not found
        or if an LDAP error occurs.
    """
    conn = None
    try:
        conn = ldap.initialize(LDAP_SERVER_URI)
        conn.set_option(ldap.OPT_PROTOCOL_VERSION, 3)
        # Set OPT_REFERRALS to 0, especially for Active Directory
        conn.set_option(ldap.OPT_REFERRALS, 0)

        # Attempt to bind to the server
        conn.simple_bind_s(LDAP_BIND_DN, LDAP_BIND_PASSWORD)

        search_filter = LDAP_USER_SEARCH_FILTER.format(username=username)

        # Perform the search
        results = conn.search_s(
            LDAP_BASE_DN,
            ldap.SCOPE_SUBTREE,
            search_filter,
            LDAP_ATTRIBUTES_TO_RETRIEVE,
        )

        if not results:
            return None  # User not found

        # Results are a list of tuples: [(dn, {attr: [values]})]
        _dn, entry = results[0]

        # LDAP attributes are returned as bytes, so they need to be decoded.
        # The values are lists; we typically want the first item.
        def get_attr_value(attr_name: str) -> str:
            value_bytes = entry.get(attr_name.encode("utf-8"), [b""])[0]
            return value_bytes.decode("utf-8")

        user_details = {
            "fullName": get_attr_value(ATTR_FULL_NAME),
            "email": get_attr_value(ATTR_EMAIL),
            "department": get_attr_value(ATTR_DEPARTMENT),
        }

        return user_details

    except ldap.LDAPError:
        # In a real application, you would log the specific error.
        # For example: logging.error(f"LDAP error for user {username}: {e}")
        return None
    finally:
        if conn:
            try:
                conn.unbind_s()
            except ldap.LDAPError:
                # Log unbind error if necessary, but don't raise
                pass


if __name__ == "__main__":
    # This is an example of how to use the function.
    # You must have a running LDAP server and valid credentials for this to work.
    # Replace 'testuser' with a username that exists in your LDAP directory.
    test_username = "testuser"

    print(f"Attempting to look up details for user: '{test_username}'...")
    print("---")
    print(f"LDAP Server: {LDAP_SERVER_URI}")
    print(f"Base DN: {LDAP_BASE_DN}")
    print(f"Bind DN: {LDAP_BIND_DN}")
    print("---")

    # Note: The following call will likely fail unless you have updated the
    # placeholder configuration constants at the top of this file.
    details = get_ldap_user_details(test_username)

    if details:
        print("User found!")
        print(f"  Full Name:  {details['fullName']}")
        print(f"  Email:      {details['email']}")
        print(f"  Department: {details['department']}")
    else:
        print(
            f"Could not retrieve details for user '{test_username}'. "
            "The user may not exist, or there might be an LDAP configuration "
            "or connection error."
        )
