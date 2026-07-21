from fastapi.testclient import TestClient

from app.main import app


def test_create_and_route_order() -> None:
    client = TestClient(app)

    create_response = client.post(
        "/v1/orders",
        json={
            "external_order_id": "ext-1001",
            "source_system": "storefront",
            "destination_system": "erp",
            "customer_id": "customer-123",
            "items": [
                {"sku": "ABC-1", "quantity": 2, "unit_price": "10.50"},
                {"sku": "XYZ-9", "quantity": 1, "unit_price": "5.00"},
            ],
            "metadata": {"channel": "web"},
        },
    )

    assert create_response.status_code == 201
    order = create_response.json()
    assert order["status"] == "validated"
    assert order["total_amount"] == "26.00"

    route_response = client.post(
        f"/v1/orders/{order['id']}/route",
        json={"integration_name": "erp", "transport_reference": "erp-queue-1"},
    )

    assert route_response.status_code == 200
    routed_order = route_response.json()
    assert routed_order["status"] == "routed"
    assert routed_order["integration_name"] == "erp"
    assert routed_order["transport_reference"] == "erp-queue-1"

