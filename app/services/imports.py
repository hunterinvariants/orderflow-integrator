from __future__ import annotations

import csv
import io
import json

from app.schemas.order import OrderCreateRequest


REQUIRED_COLUMNS = {"external_order_id", "source_system", "destination_system", "customer_id", "items"}


def parse_order_csv(content: bytes) -> list[OrderCreateRequest]:
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    if not reader.fieldnames or not REQUIRED_COLUMNS.issubset(reader.fieldnames):
        missing = sorted(REQUIRED_COLUMNS.difference(reader.fieldnames or []))
        raise ValueError(f"Missing CSV columns: {', '.join(missing)}")
    orders = []
    for row_number, row in enumerate(reader, start=2):
        try:
            items = json.loads(row["items"])
            metadata = json.loads(row.get("metadata") or "{}")
            orders.append(OrderCreateRequest(
                external_order_id=row["external_order_id"], source_system=row["source_system"],
                destination_system=row["destination_system"], customer_id=row["customer_id"],
                currency=row.get("currency") or None, items=items, notes=row.get("notes") or None, metadata=metadata,
            ))
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid CSV row {row_number}: {exc}") from exc
    return orders
