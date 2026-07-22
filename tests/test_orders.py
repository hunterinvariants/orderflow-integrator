from fastapi.testclient import TestClient


def order_payload(external_id: str = "ext-1001", total: str = "10.50") -> dict:
    return {
        "external_order_id": external_id,
        "source_system": "storefront",
        "destination_system": "erp",
        "customer_id": "customer-123",
        "items": [{"sku": "ABC-1", "quantity": 2, "unit_price": total}],
        "metadata": {"channel": "web"},
    }


def test_create_route_and_process_order(client: TestClient) -> None:
    create_response = client.post("/v1/orders", json=order_payload())
    assert create_response.status_code == 201
    order = create_response.json()
    assert order["status"] == "validated"
    assert order["total_amount"] == "21.00"

    route_response = client.post(f"/v1/orders/{order['id']}/route", json={"integration_name": "erp", "process_async": False})
    assert route_response.status_code == 200
    assert route_response.json()["integration_name"] == "erp"

    synced = client.app.state.orderflow.process_order(order["id"])
    assert synced.status == "synced"
    assert synced.transport_reference.startswith("NETSUITE-")
    assert len(synced.events) == 5


def test_duplicate_order_is_rejected(client: TestClient) -> None:
    assert client.post("/v1/orders", json=order_payload("duplicate")).status_code == 201
    response = client.post("/v1/orders", json=order_payload("duplicate"))
    assert response.status_code == 409


def test_high_value_order_uses_sap_rule(client: TestClient) -> None:
    response = client.post("/v1/orders", json=order_payload("high-value", "600.00"))
    order = response.json()
    routed = client.post(f"/v1/orders/{order['id']}/route", json={"process_async": False}).json()
    assert routed["integration_name"] == "sap"


def test_connector_failure_is_audited(client: TestClient) -> None:
    order = client.post("/v1/orders", json=order_payload("FAIL-TEST")).json()
    routed = client.post(f"/v1/orders/{order['id']}/route", json={"process_async": False}).json()
    try:
        client.app.state.orderflow.process_order(routed["id"])
    except RuntimeError:
        pass
    failed = client.get(f"/v1/orders/{order['id']}").json()
    assert failed["status"] == "failed"
    assert failed["delivery_attempts"] == 1
    assert failed["last_error"]
