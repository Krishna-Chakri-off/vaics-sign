"""Built-in roles and permissions (FRS §5)."""
ROLES = ("org_admin", "sender", "template_manager", "auditor", "viewer")
P = {
    "users.manage": {"org_admin"},
    "settings.manage": {"org_admin"},
    "templates.share": {"org_admin", "template_manager"},
    "templates.create": {"org_admin", "template_manager", "sender"},
    "envelopes.send": {"org_admin", "sender", "template_manager"},
    "bulk.send": {"org_admin", "sender", "template_manager"},
    "envelopes.view_all": {"org_admin", "auditor"},
    "envelopes.view_own": {"org_admin", "sender", "template_manager"},
    "audit.view": {"org_admin", "auditor", "sender", "template_manager"},
    "privacy.manage": {"org_admin", "auditor"},
    "reports.view": {"org_admin", "auditor"},
}

def has_perm(role: str, perm: str) -> bool:
    return role in P.get(perm, set())
