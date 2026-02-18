import os
from dataclasses import dataclass
from typing import Optional

from ldap3 import ALL, SUBTREE, Connection, Server, Tls
from ldap3.core.exceptions import LDAPException, LDAPSocketOpenError
from ldap3.utils.conv import escape_filter_chars


@dataclass(frozen=True)
class UserDetails:
    full_name: Optional[str]
    email: Optional[str]
    department: Optional[str]


class LDAPLookupError(RuntimeError):
    pass


def lookup_user_details(username: str) -> Optional[UserDetails]:
    """
    Look up a user's details in LDAP by username.

    Configuration via environment variables:
      - LDAP_SERVER_URI (e.g., "ldaps://ldap.example.com:636")
      - LDAP_BIND_DN
      - LDAP_BIND_PASSWORD
      - LDAP_BASE_DN (e.g., "dc=example,dc=com")
      - LDAP_USERNAME_ATTRIBUTE (default: "uid"; for AD often "sAMAccountName")
      - LDAP_USE_SSL ("true"/"false"; default derived from URI)
      - LDAP_TLS_VALIDATE ("none"/"required"; default: "required")
      - LDAP_CONNECT_TIMEOUT_SECONDS (default: 10)
      - LDAP_RECEIVE_TIMEOUT_SECONDS (default: 10)
    """
    if not isinstance(username, str) or not username.strip():
        raise ValueError("username must be a non-empty string")

    server_uri = os.environ.get("LDAP_SERVER_URI")
    bind_dn = os.environ.get("LDAP_BIND_DN")
    bind_password = os.environ.get("LDAP_BIND_PASSWORD")
    base_dn = os.environ.get("LDAP_BASE_DN")
    username_attr = os.environ.get("LDAP_USERNAME_ATTRIBUTE", "uid").strip() or "uid"

    if not server_uri or not bind_dn or bind_password is None or not base_dn:
        raise LDAPLookupError(
            "Missing LDAP configuration. Required: LDAP_SERVER_URI, LDAP_BIND_DN, LDAP_BIND_PASSWORD, LDAP_BASE_DN."
        )

    connect_timeout = int(os.environ.get("LDAP_CONNECT_TIMEOUT_SECONDS", "10"))
    receive_timeout = int(os.environ.get("LDAP_RECEIVE_TIMEOUT_SECONDS", "10"))

    use_ssl_env = os.environ.get("LDAP_USE_SSL", "").strip().lower()
    use_ssl = server_uri.lower().startswith("ldaps://") if use_ssl_env == "" else use_ssl_env in {"1", "true", "yes", "on"}

    tls_validate_env = os.environ.get("LDAP_TLS_VALIDATE", "required").strip().lower()
    if tls_validate_env == "none":
        tls = Tls(validate=0)  # ssl.CERT_NONE
    else:
        tls = Tls()  # default: CERT_REQUIRED in most environments

    server = Server(
        server_uri,
        use_ssl=use_ssl,
        tls=tls,
        get_info=ALL,
        connect_timeout=connect_timeout,
    )

    escaped_username = escape_filter_chars(username.strip())
    search_filter = f"({username_attr}={escaped_username})"
    attributes = ["displayName", "cn", "mail", "department"]

    try:
        with Connection(
            server,
            user=bind_dn,
            password=bind_password,
            auto_bind=True,
            receive_timeout=receive_timeout,
            raise_exceptions=True,
        ) as conn:
            conn.search(
                search_base=base_dn,
                search_filter=search_filter,
                search_scope=SUBTREE,
                attributes=attributes,
                size_limit=2,
            )

            if not conn.entries:
                return None

            entry = conn.entries[0]
            data = entry.entry_attributes_as_dict

            full_name = None
            for key in ("displayName", "cn"):
                val = data.get(key)
                if isinstance(val, list) and val:
                    full_name = str(val[0])
                    break
                if isinstance(val, str) and val:
                    full_name = val
                    break

            email_val = data.get("mail")
            department_val = data.get("department")

            email = (
                str(email_val[0]) if isinstance(email_val, list) and email_val else (email_val if isinstance(email_val, str) else None)
            )
            department = (
                str(department_val[0])
                if isinstance(department_val, list) and department_val
                else (department_val if isinstance(department_val, str) else None)
            )

            return UserDetails(full_name=full_name, email=email, department=department)

    except LDAPSocketOpenError as e:
        raise LDAPLookupError(f"Unable to connect to LDAP server: {e}") from e
    except LDAPException as e:
        raise LDAPLookupError(f"LDAP operation failed: {e}") from e
