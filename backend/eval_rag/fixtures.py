"""
Synthetic log corpus for RAG evaluation.

The corpus is deterministic: five incidents with hand-crafted log sequences the
Q&A dataset's ground-truth answers are derived from, plus benign filler so the
retriever can't trivially return everything.

Each log is a dict matching SignalOps' /logs/ingest body:
    {service, level, message, trace_id, metadata, timestamp}

Timestamps are built relative to BASE_TS so re-ingesting the corpus produces a
stable ordering.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

BASE_TS = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)


def _at(mins: int, secs: int = 0) -> str:
    return (BASE_TS + timedelta(minutes=mins, seconds=secs)).isoformat()


def _log(service: str, level: str, message: str, mins: int, trace: str,
         secs: int = 0, **meta: Any) -> dict[str, Any]:
    return {
        "service": service,
        "level": level,
        "message": message,
        "trace_id": trace,
        "metadata": meta,
        "timestamp": _at(mins, secs),
    }


# ---------------------------------------------------------------------------
# Incident A: payment gateway timeout cascade (12:00 - 12:05)
# Root cause: stripe gateway returned 504 for 23 payments across 5 min window.
# ---------------------------------------------------------------------------
INCIDENT_A = [
    _log("payment-service", "INFO", "Payment gateway health check: ok", 0, "pay-hc-01", gateway="stripe"),
    _log("payment-service", "ERROR", "Payment gateway timeout after 30s", 1, "pay-A01", gateway="stripe", retry_count=3, order_id="ord_1001"),
    _log("payment-service", "ERROR", "Payment gateway timeout after 30s", 1, "pay-A02", secs=15, gateway="stripe", retry_count=3, order_id="ord_1002"),
    _log("payment-service", "ERROR", "Payment gateway timeout after 30s", 1, "pay-A03", secs=30, gateway="stripe", retry_count=3, order_id="ord_1003"),
    _log("payment-service", "ERROR", "Payment gateway timeout after 30s", 2, "pay-A04", gateway="stripe", retry_count=3, order_id="ord_1004"),
    _log("payment-service", "ERROR", "Payment gateway returned HTTP 504", 2, "pay-A05", secs=20, gateway="stripe", status=504, order_id="ord_1005"),
    _log("payment-service", "ERROR", "Payment gateway returned HTTP 504", 2, "pay-A06", secs=40, gateway="stripe", status=504, order_id="ord_1006"),
    _log("payment-service", "ERROR", "Payment gateway returned HTTP 504", 3, "pay-A07", gateway="stripe", status=504, order_id="ord_1007"),
    _log("payment-service", "ERROR", "Payment gateway returned HTTP 504", 3, "pay-A08", secs=20, gateway="stripe", status=504, order_id="ord_1008"),
    _log("payment-service", "ERROR", "Payment gateway returned HTTP 504", 3, "pay-A09", secs=40, gateway="stripe", status=504, order_id="ord_1009"),
    _log("payment-service", "ERROR", "Payment gateway timeout after 30s", 4, "pay-A10", gateway="stripe", retry_count=3, order_id="ord_1010"),
    _log("payment-service", "ERROR", "Payment gateway timeout after 30s", 4, "pay-A11", secs=15, gateway="stripe", retry_count=3, order_id="ord_1011"),
    _log("payment-service", "ERROR", "Payment gateway returned HTTP 504", 4, "pay-A12", secs=30, gateway="stripe", status=504, order_id="ord_1012"),
    _log("payment-service", "ERROR", "Payment gateway returned HTTP 504", 4, "pay-A13", secs=45, gateway="stripe", status=504, order_id="ord_1013"),
    _log("payment-service", "ERROR", "Payment gateway timeout after 30s", 5, "pay-A14", gateway="stripe", retry_count=3, order_id="ord_1014"),
    _log("payment-service", "ERROR", "Payment gateway returned HTTP 504", 5, "pay-A15", secs=15, gateway="stripe", status=504, order_id="ord_1015"),
    _log("payment-service", "ERROR", "Payment gateway returned HTTP 504", 5, "pay-A16", secs=30, gateway="stripe", status=504, order_id="ord_1016"),
    _log("payment-service", "ERROR", "Payment gateway timeout after 30s", 5, "pay-A17", secs=45, gateway="stripe", retry_count=3, order_id="ord_1017"),
    _log("payment-service", "ERROR", "Payment gateway returned HTTP 504", 5, "pay-A18", secs=50, gateway="stripe", status=504, order_id="ord_1018"),
    _log("payment-service", "ERROR", "Payment gateway timeout after 30s", 5, "pay-A19", secs=55, gateway="stripe", retry_count=3, order_id="ord_1019"),
    _log("payment-service", "ERROR", "Payment gateway returned HTTP 504", 6, "pay-A20", gateway="stripe", status=504, order_id="ord_1020"),
    _log("payment-service", "ERROR", "Payment gateway returned HTTP 504", 6, "pay-A21", secs=10, gateway="stripe", status=504, order_id="ord_1021"),
    _log("payment-service", "ERROR", "Payment gateway timeout after 30s", 6, "pay-A22", secs=20, gateway="stripe", retry_count=3, order_id="ord_1022"),
    _log("payment-service", "ERROR", "Payment gateway timeout after 30s", 6, "pay-A23", secs=30, gateway="stripe", retry_count=3, order_id="ord_1023"),
    _log("payment-service", "INFO", "Stripe status page confirms incident sev2 for US-East", 7, "pay-ext-01"),
    _log("payment-service", "INFO", "Payment gateway health check: ok", 15, "pay-hc-02", gateway="stripe"),
]

# ---------------------------------------------------------------------------
# Incident B: auth brute-force attempt (12:20 - 12:23)
# Root cause: 47 failed login attempts for user_id=user_789 from 203.0.113.42
# ---------------------------------------------------------------------------
INCIDENT_B_IP = "203.0.113.42"
INCIDENT_B_USER = "user_789"
INCIDENT_B = []
for i in range(47):
    INCIDENT_B.append(_log(
        "auth-service", "WARN",
        f"Failed login attempt for user_id={INCIDENT_B_USER}", 20, f"auth-B{i:02d}",
        secs=(i * 4) % 180, user_id=INCIDENT_B_USER, ip=INCIDENT_B_IP, reason="bad_password",
    ))
INCIDENT_B.extend([
    _log("auth-service", "ERROR", f"Account locked after 47 failed attempts: {INCIDENT_B_USER}", 23, "auth-B-lock",
         user_id=INCIDENT_B_USER, ip=INCIDENT_B_IP, action="lock_account", threshold=10),
    _log("auth-service", "INFO", "User login successful", 24, "auth-B-norm1",
         user_id="user_123", method="oauth"),
])

# ---------------------------------------------------------------------------
# Incident C: DB slow query from missing index (12:30 - 12:34)
# Root cause: SELECT * FROM orders WHERE user_id = $1 missing an index
#   Fix mentioned in log: CREATE INDEX ix_orders_user_id ON orders(user_id)
# ---------------------------------------------------------------------------
INCIDENT_C = [
    _log("db-service", "WARN", "Slow query detected (3.1s): SELECT * FROM orders WHERE user_id = $1", 30, "db-C01",
         query_time_ms=3100, table="orders"),
    _log("db-service", "WARN", "Slow query detected (3.4s): SELECT * FROM orders WHERE user_id = $1", 31, "db-C02",
         query_time_ms=3400, table="orders"),
    _log("db-service", "WARN", "Slow query detected (3.8s): SELECT * FROM orders WHERE user_id = $1", 32, "db-C03",
         query_time_ms=3800, table="orders"),
    _log("db-service", "WARN", "Slow query detected (4.2s): SELECT * FROM orders WHERE user_id = $1", 33, "db-C04",
         query_time_ms=4200, table="orders"),
    _log("db-service", "INFO", "Running EXPLAIN on slow query", 33, "db-C05", secs=30),
    _log("db-service", "INFO", "EXPLAIN output: Seq Scan on orders (cost=0..18420 rows=1)", 33, "db-C06", secs=45),
    _log("db-service", "INFO", "Applying remediation: CREATE INDEX ix_orders_user_id ON orders(user_id)", 34, "db-C07"),
    _log("db-service", "INFO", "Index created successfully: ix_orders_user_id", 34, "db-C08", secs=30),
    _log("db-service", "INFO", "Slow query no longer detected after index creation", 35, "db-C09"),
]

# ---------------------------------------------------------------------------
# Incident D: bad deploy regression (12:40 - 12:45)
# Root cause: api-gateway v2.14.3 returned 500 on /api/v1/products,
#   rolled back to v2.14.2 at 12:44.
# ---------------------------------------------------------------------------
INCIDENT_D = [
    _log("api-gateway", "INFO", "Deploy started: v2.14.3", 40, "api-D-dep", version="2.14.3"),
    _log("api-gateway", "INFO", "Deploy complete: v2.14.3", 40, "api-D-ok", secs=45, version="2.14.3"),
    _log("api-gateway", "ERROR", "500 Internal Server Error on GET /api/v1/products", 41, "api-D01",
         path="/api/v1/products", status=500, version="2.14.3"),
    _log("api-gateway", "ERROR", "500 Internal Server Error on GET /api/v1/products", 41, "api-D02", secs=20,
         path="/api/v1/products", status=500, version="2.14.3"),
    _log("api-gateway", "ERROR", "500 Internal Server Error on GET /api/v1/products", 42, "api-D03",
         path="/api/v1/products", status=500, version="2.14.3"),
    _log("api-gateway", "ERROR", "500 Internal Server Error on GET /api/v1/products", 42, "api-D04", secs=15,
         path="/api/v1/products", status=500, version="2.14.3"),
    _log("api-gateway", "ERROR", "500 Internal Server Error on GET /api/v1/products", 42, "api-D05", secs=30,
         path="/api/v1/products", status=500, version="2.14.3"),
    _log("api-gateway", "ERROR", "500 Internal Server Error on GET /api/v1/products", 43, "api-D06",
         path="/api/v1/products", status=500, version="2.14.3"),
    _log("api-gateway", "WARN", "Error rate above 5% for /api/v1/products, considering rollback", 43, "api-D-warn", secs=30),
    _log("api-gateway", "INFO", "Rollback initiated: v2.14.3 -> v2.14.2", 44, "api-D-rb", version_from="2.14.3", version_to="2.14.2"),
    _log("api-gateway", "INFO", "Rollback complete: v2.14.2 restored", 44, "api-D-rb-ok", secs=40, version="2.14.2"),
    _log("api-gateway", "INFO", "GET /api/v1/products 200 OK (post-rollback)", 45, "api-D-norm",
         path="/api/v1/products", status=200, version="2.14.2"),
]

# ---------------------------------------------------------------------------
# Incident E: order-service inventory failure (12:50 - 12:53)
# Root cause: SKU-456 (product "Blue Widget") out of stock, 11 orders failed.
# ---------------------------------------------------------------------------
INCIDENT_E = []
for i in range(11):
    INCIDENT_E.append(_log(
        "order-service", "ERROR",
        f"Inventory check failed for product SKU-456 (Blue Widget)", 50, f"ord-E{i:02d}",
        secs=i * 10, order_id=f"ord_20{i:02d}", sku="SKU-456", product_name="Blue Widget", reason="out_of_stock",
    ))
INCIDENT_E.extend([
    _log("order-service", "INFO", "Inventory restocked for SKU-456 (Blue Widget): 100 units", 53, "ord-E-restock",
         sku="SKU-456", added=100),
    _log("order-service", "INFO", "Order created successfully", 54, "ord-E-norm", order_id="ord_2100", status="pending"),
])

# ---------------------------------------------------------------------------
# Filler: benign normal-ops logs spread over the hour so the retriever has to
# actually search instead of returning everything.
# ---------------------------------------------------------------------------
FILLER = []
_filler_svcs = ["api-gateway", "auth-service", "order-service", "db-service", "payment-service", "notification-service"]
for i in range(80):
    svc = _filler_svcs[i % len(_filler_svcs)]
    mins = (i * 7) % 60
    FILLER.append(_log(svc, "INFO", f"heartbeat #{i}: service healthy", mins, f"filler-{i:03d}",
                      secs=(i * 11) % 60, iteration=i))


ALL_LOGS: list[dict[str, Any]] = (
    INCIDENT_A + INCIDENT_B + INCIDENT_C + INCIDENT_D + INCIDENT_E + FILLER
)


if __name__ == "__main__":
    import json
    print(json.dumps({
        "total": len(ALL_LOGS),
        "by_incident": {
            "A_payment_timeout": len(INCIDENT_A),
            "B_auth_bruteforce": len(INCIDENT_B),
            "C_db_slow_query": len(INCIDENT_C),
            "D_bad_deploy": len(INCIDENT_D),
            "E_inventory_fail": len(INCIDENT_E),
            "filler": len(FILLER),
        },
    }, indent=2))
