from __future__ import annotations

import json
import sys
import urllib.request


BASE = "http://127.0.0.1:8000"


def req(path: str, *, method: str = "GET", data=None, headers: dict | None = None):
    headers = headers or {}
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    r = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    with urllib.request.urlopen(r, timeout=10) as resp:
        raw = resp.read().decode("utf-8")
        return resp.status, (json.loads(raw) if raw else None)


def main() -> int:
    # login
    st, j = req(
        "/auth/login",
        method="POST",
        data={"username": "accountant", "password": "accountant123"},
    )
    assert st == 200 and j and "access_token" in j, (st, j)
    token = j["access_token"]
    H = {"Authorization": "Bearer " + token}

    # book
    st, books = req("/books", headers=H)
    assert st == 200 and books, (st, books)
    book_id = books[0]["id"]

    # find 1001
    st, tree = req("/accounts/tree?book_id=" + book_id, headers=H)
    assert st == 200 and tree, (st, tree)

    stack = list(tree)
    acc_1001 = None
    while stack:
        n = stack.pop()
        if n.get("code") == "1001":
            acc_1001 = n["id"]
            break
        stack.extend(n.get("children") or [])
    assert acc_1001, "missing account code 1001"

    payload = {
        "book_id": book_id,
        "account_id": acc_1001,
        "statement_date": "2025-12-22",
        "ending_balance": 0,
    }

    st1, s1 = req("/reconcile/sessions", method="POST", data=payload, headers=H)
    st2, s2 = req("/reconcile/sessions", method="POST", data=payload, headers=H)

    print("create1", st1, s1.get("id"))
    print("create2", st2, s2.get("id"))
    print("same", s1.get("id") == s2.get("id"))
    assert st1 == 200 and st2 == 200, (st1, st2, s1, s2)
    assert s1.get("id") == s2.get("id"), (s1, s2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


