from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1

from app.models import OrderModel


class ConnectorDeliveryError(RuntimeError):
    pass


@dataclass(frozen=True)
class ConnectorProfile:
    name: str
    label: str
    description: str
    protocol: str
    accent: str


class MockConnector:
    def __init__(self, profile: ConnectorProfile) -> None:
        self.profile = profile

    def send(self, order: OrderModel) -> str:
        # External IDs containing FAIL create a repeatable dead-letter demo.
        if "FAIL" in order.external_order_id.upper():
            raise ConnectorDeliveryError(f"{self.profile.label} rejected the simulated payload")
        digest = sha1(f"{self.profile.name}:{order.external_order_id}".encode()).hexdigest()[:10].upper()
        return f"{self.profile.name.upper()}-{digest}"


CONNECTORS = {
    profile.name: MockConnector(profile)
    for profile in [
        ConnectorProfile("netsuite", "NetSuite ERP", "Financial posting and inventory reservation", "REST", "#ef5b2a"),
        ConnectorProfile("sap", "SAP S/4HANA", "High-value enterprise order orchestration", "OData", "#0f6cbd"),
        ConnectorProfile("shipstation", "ShipStation", "Carrier selection and shipment creation", "REST", "#16a085"),
        ConnectorProfile("warehouse", "Warehouse WMS", "Pick, pack, and fulfillment handoff", "Webhook", "#d29b2f"),
    ]
}
# Backward-compatible API names map to the richer demo connectors.
CONNECTORS["erp"] = CONNECTORS["netsuite"]
CONNECTORS["wms"] = CONNECTORS["warehouse"]
CONNECTORS["shipping"] = CONNECTORS["shipstation"]
