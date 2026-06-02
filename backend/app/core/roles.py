"""Role identity helpers.

Role names are the stable identity for built-in privileged roles. Usernames are
not used for authorization decisions.
"""

ROLE_ADMIN = "admin"
ROLE_SUPER_ADMIN = "super_admin"
ADMIN_ROLE_NAMES = {ROLE_ADMIN, ROLE_SUPER_ADMIN}
PROTECTED_ROLE_NAMES = {ROLE_ADMIN, ROLE_SUPER_ADMIN}


def role_name(user) -> str | None:
    return getattr(getattr(user, "role", None), "name", None)


def is_super_admin(user) -> bool:
    return role_name(user) == ROLE_SUPER_ADMIN


def is_admin(user) -> bool:
    return role_name(user) in ADMIN_ROLE_NAMES


def is_protected_role_name(name: str | None) -> bool:
    return name in PROTECTED_ROLE_NAMES
