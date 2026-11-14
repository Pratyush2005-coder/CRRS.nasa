# Phase 4.7A Dependency Security Investigation — Executive Summary

**Bottom Line: MIGRATE TO PyJWT** — Eliminates all 3 vulnerabilities permanently with ~15 line changes.

---

## Vulnerability Summary

| Package | Version | Vulnerability | Exploitable? |
|---------|---------|---------------|--------------|
| python-jose | 3.5.0 | PYSEC-2026-4298 (CVE-2026-85394) | **NO** — HS256 pinning prevents |
| ecdsa | 0.19.2 | PYSEC-2026-1325 (CVE-2024-23342) x2 | **NO** — ECDSA code paths never used |

**Architectural Mitigation:** Application uses **HS256 only** with explicit `algorithms=["HS256"]` pinning in `jwt.decode()`. Both vulnerabilities require code paths that are never executed.

---

## Dependency Tree

```
python-jose==3.5.0 (DIRECT)
├── ecdsa==0.19.2 (transitive) ← **VULNERABLE, unused**
├── rsa==4.9.1 (transitive)
└── pyasn1==0.6.5 (transitive)
```

**Removing python-jose eliminates ecdsa entirely.** No other package depends on it.

---

## PyJWT Migration: What Changes

### requirements.txt
```diff
- python-jose[cryptography]>=3.3.0
+ PyJWT>=2.8.0
```

### app/core/security.py (~15 lines)
```python
# Import change
- from jose import JWTError, jwt
+ import jwt
+ from jwt import PyJWTError as JWTError, ExpiredSignatureError

# encode() — IDENTICAL API
# decode() — IDENTICAL API  
# Exception handling — minor adjustment (PyJWTError vs JWTError)
# get_unverified_claims() → decode(token, options={"verify_signature": False})
```

### tests/test_security.py
- Import `jwt` from PyJWT instead of jose (test helper only)
- All 78 existing tests should pass unchanged

---

## Regression Test Plan

| Phase | Command | Target |
|-------|---------|--------|
| Unit | `pytest tests/test_security.py -v` | 78 tests pass |
| Auth | `pytest tests/test_auth.py -v` | 27 tests pass |
| Full | `pytest tests/ -v` | 482 tests pass |
| Security | `pip-audit -r requirements.txt` | **0 vulnerabilities** |

---

## Rollback (if needed)
```bash
git checkout requirements.txt app/core/security.py tests/test_security.py
pip install -r requirements.txt
# < 5 minutes
```

---

## Why Not Wait for python-jose Fix?

1. **No fix version exists** for PYSEC-2026-4298
2. **ecdsa upstream refuses to fix** timing attack (considers side-channels out of scope)
3. **PyJWT is strictly better** for HS256: zero deps, stdlib-only, actively maintained
4. **Migration is trivial** — same API surface for symmetric algorithms

---

*Full report: `PHASE_4.7A_DEPENDENCY_SECURITY_INVESTIGATION.md`*