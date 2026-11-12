#!/usr/bin/env python3
"""
UniMonitor post-install smoke test.
Verifies the API is running and core endpoints respond correctly.
"""
import asyncio
import sys
import os
import httpx

BASE_URL = os.getenv("UNIMONITOR_URL", "http://localhost:8000")
ADMIN_EMAIL = os.getenv("UNIMONITOR_ADMIN_EMAIL", "admin@unimonitor.local")
ADMIN_PASSWORD = os.getenv("UNIMONITOR_ADMIN_PASSWORD", "")

PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"


async def test_health(client: httpx.AsyncClient) -> bool:
    """Test /api/v1/health returns 200."""
    try:
        r = await client.get(f"{BASE_URL}/api/v1/health")
        ok = r.status_code == 200
        status = r.json().get("status", "unknown")
        print(f"  {PASS if ok else FAIL} Health check: {r.status_code} ({status})")
        return ok
    except Exception as e:
        print(f"  {FAIL} Health check: {e}")
        return False


async def test_login(client: httpx.AsyncClient) -> str | None:
    """Test /api/v1/auth/login returns a token."""
    if not ADMIN_PASSWORD:
        print(f"  ⚠  Login: skipped (set UNIMONITOR_ADMIN_PASSWORD env var)")
        return None
    try:
        r = await client.post(
            f"{BASE_URL}/api/v1/auth/login",
            data={"username": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        ok = r.status_code == 200 and "access_token" in r.json()
        print(f"  {PASS if ok else FAIL} Login ({ADMIN_EMAIL}): {r.status_code}")
        return r.json().get("access_token") if ok else None
    except Exception as e:
        print(f"  {FAIL} Login: {e}")
        return None


async def test_authenticated_endpoints(client: httpx.AsyncClient, token: str) -> dict[str, bool]:
    """Test core authenticated endpoints."""
    headers = {"Authorization": f"Bearer {token}"}
    results = {}

    endpoints = [
        ("GET", "/api/v1/assessments", "List assessments"),
        ("GET", "/api/v1/findings", "List findings"),
        ("GET", "/api/v1/reports", "List reports"),
        ("GET", "/api/v1/monitoring/health", "Monitoring health"),
        ("GET", "/api/v1/monitoring/collectors", "Collector status"),
        ("GET", "/api/v1/dashboard/executive", "Executive dashboard"),
    ]

    for method, path, label in endpoints:
        try:
            r = await client.request(method, f"{BASE_URL}{path}", headers=headers)
            ok = r.status_code in (200, 201, 204)
            print(f"  {PASS if ok else FAIL} {label}: {r.status_code}")
            results[label] = ok
        except Exception as e:
            print(f"  {FAIL} {label}: {e}")
            results[label] = False

    return results


async def test_static_assets(client: httpx.AsyncClient) -> bool:
    """Test that the frontend is served."""
    try:
        r = await client.get(f"{BASE_URL}/")
        ok = r.status_code == 200 and "text/html" in r.headers.get("content-type", "")
        print(f"  {PASS if ok else FAIL} Frontend (index.html): {r.status_code}")
        return ok
    except Exception as e:
        print(f"  {FAIL} Frontend: {e}")
        return False


async def main() -> None:
    print("=" * 60)
    print("  UniMonitor Smoke Test")
    print(f"  Target: {BASE_URL}")
    print("=" * 60)
    print()

    all_pass = True

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        print("Basic connectivity:")
        health_ok = await test_health(client)
        all_pass &= health_ok

        print()
        print("Frontend:")
        static_ok = await test_static_assets(client)
        all_pass &= static_ok

        print()
        print("Authentication:")
        token = await test_login(client)

        if token:
            print()
            print("API endpoints:")
            results = await test_authenticated_endpoints(client, token)
            all_pass &= all(results.values())

    print()
    print("=" * 60)
    if all_pass:
        print("  \033[92mAll tests passed! UniMonitor is healthy.\033[0m")
        sys.exit(0)
    else:
        print("  \033[91mSome tests FAILED. Check the output above.\033[0m")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
