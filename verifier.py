"""
Verifier - knowledge-base cross-validation for review findings.

Every POSITIVE finding must cite an evidence snippet that actually
exists in the artifact it claims to describe. Unverifiable findings
are QUARANTINED, not silently dropped: suspected hallucinations stay
visible (transparency) but never reach the repair loop or approvals.

Exemption: level "OK" findings are absence claims ("no problem here")
and cannot cite evidence by nature - they pass by definition.
"""


def verify_findings(findings, artifacts):
    """Split findings into (verified, quarantined).

    A finding is verified iff its evidence is a non-empty substring of
    the cited artifact. Quarantined entries carry a quarantine_reason.
    """
    verified, quarantined = [], []
    for f in findings:
        if f["level"] == "OK":
            verified.append(f)
            continue
        evidence = f.get("evidence", "")
        artifact = artifacts.get(f["task"], "")
        if evidence and evidence in artifact:
            verified.append(f)
        else:
            reason = "证据缺失" if not evidence else "证据与代码不符"
            quarantined.append({**f, "quarantine_reason": reason})
    return verified, quarantined
