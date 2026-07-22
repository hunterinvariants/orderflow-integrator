from decimal import Decimal

from app.core.config import get_settings
from app.database import create_schema
from app.schemas.order import OrderCreateRequest, OrderRouteRequest
from app.services.order_flow import DuplicateOrderError, OrderFlowService


DEMO_ORDERS = [
    ("SHOP-10481", "shopify", "erp", "ACME Retail", Decimal("184.40"), "4"),
    ("AMZ-77429", "amazon", "wms", "Northstar Goods", Decimal("68.50"), "2"),
    ("B2B-93018", "salesforce", "erp", "Helios Trading", Decimal("2450.00"), "10"),
    ("SHOP-10482", "shopify", "shipping", "Mira Home", Decimal("129.99"), "1"),
    ("FAIL-2207", "magento", "wms", "Failure Demo", Decimal("84.25"), "1"),
]


def seed_demo_data(service: OrderFlowService | None = None) -> list[str]:
    if service is None:
        create_schema()
        service = OrderFlowService(get_settings())
    service.ensure_default_rules()
    seeded = []
    for external_id, source, destination, customer, amount, quantity in DEMO_ORDERS:
        try:
            quantity_value = int(quantity)
            order = service.create_order(OrderCreateRequest(
                external_order_id=external_id,
                source_system=source,
                destination_system=destination,
                customer_id=customer,
                currency="USD",
                items=[{"sku": f"SKU-{external_id[-4:]}", "quantity": quantity_value, "unit_price": amount / quantity_value}],
                metadata={"channel": source, "demo": True},
            ))
            routed = service.route_order(order.id, OrderRouteRequest(process_async=False))
            try:
                service.process_order(routed.id)
            except RuntimeError:
                pass
            seeded.append(external_id)
        except DuplicateOrderError:
            continue
    return seeded


if __name__ == "__main__":
    print(f"Seeded {len(seed_demo_data())} demo orders")
