import json

from fastapi.testclient import TestClient


PAYLOAD = {
    "external_order_id": "WEBHOOK-1",
    "source_system": "shopify",
    "destination_system": "shipping",
    "customer_id": "customer-webhook",
    "items": [{"sku": "HOOK-1", "quantity": 1, "unit_price": "49.90"}],
}


def test_webhook_requires_api_key(client: TestClient) -> None:
    assert client.post("/v1/webhooks/orders", json=PAYLOAD).status_code == 401
    response = client.post("/v1/webhooks/orders", json=PAYLOAD, headers={"X-API-Key": "demo-orderflow-key"})
    assert response.status_code == 202
    assert response.json()["integration_name"] == "shipstation"


def test_csv_import_and_metrics(client: TestClient) -> None:
    items = json.dumps([{"sku": "CSV-1", "quantity": 3, "unit_price": "12.00"}]).replace('"', '""')
    csv_data = f'external_order_id,source_system,destination_system,customer_id,currency,items\nCSV-100,amazon,wms,csv-customer,USD,"{items}"\n'
    response = client.post("/v1/orders/import", files={"file": ("orders.csv", csv_data, "text/csv")})
    assert response.status_code == 201
    assert response.json()["created"] == 1
    metrics = client.get("/v1/metrics").json()
    assert metrics["total_orders"] == 1
    assert metrics["gross_value"] == "36.00"


def test_invalid_csv_reports_missing_columns(client: TestClient) -> None:
    response = client.post("/v1/orders/import", files={"file": ("orders.csv", "name,value\na,b\n", "text/csv")})
    assert response.status_code == 422
    assert "Missing CSV columns" in response.json()["detail"]


def test_demo_seed_is_idempotent(client: TestClient) -> None:
    first = client.post("/v1/demo/seed")
    second = client.post("/v1/demo/seed")
    assert first.status_code == 200
    assert first.json()["seeded"] == 5
    assert second.json()["seeded"] == 0
    assert client.get("/v1/metrics").json()["total_orders"] == 5
