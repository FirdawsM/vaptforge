"""Attack Surface Mapping taxonomy and coverage calculation.

This is the second axis for reporting: WSTG phase answers "what order did
we test in", this answers "what parts of the attack surface did we
actually touch." Every test in test_definitions.yaml should carry a
`component` (and ideally `element`) tag from this taxonomy.
"""

ATTACK_SURFACE = {
    "Frontend": ["Forms", "URL parameters", "JavaScript APIs", "DOM"],
    "HTTP layer": ["Headers", "Cookies", "Methods", "Request body"],
    "Authentication": ["Login forms", "Password reset", "Registration", "MFA"],
    "API endpoints": ["REST", "GraphQL", "WebSocket connections"],
    "File handling": ["Upload", "Download", "Path parameters"],
    "Third-party integrations": ["OAuth flows", "Payment gateways", "Webhooks"],
    "Admin interfaces": ["Admin panels", "Management APIs", "Debug endpoints"],
    "Infrastructure": ["Web server configs", "Default pages", "Error messages"],
}


def coverage(defs: list[dict]) -> dict:
    """Given the loaded test definitions (regardless of whether they ran),
    returns per-component coverage: which elements have at least one test
    defined, and which have none — a gap list, not a pass/fail score.
    """
    touched: dict[str, set[str]] = {c: set() for c in ATTACK_SURFACE}
    untagged = []

    for d in defs:
        component = d.get("component")
        element = d.get("element")
        if component not in ATTACK_SURFACE:
            untagged.append(d["wstg_id"])
            continue
        if element:
            touched[component].add(element)

    report = {}
    for component, elements in ATTACK_SURFACE.items():
        covered = sorted(touched[component])
        gaps = sorted(set(elements) - touched[component])
        report[component] = {
            "elements_total": elements,
            "elements_covered": covered,
            "elements_untested": gaps,
        }

    return {"by_component": report, "untagged_tests": untagged}
