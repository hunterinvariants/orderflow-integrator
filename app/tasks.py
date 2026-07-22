from celery.utils.log import get_task_logger

from app.celery_app import celery_app
from app.core.config import get_settings
from app.services.connectors import ConnectorDeliveryError
from app.services.order_flow import OrderFlowService

logger = get_task_logger(__name__)


@celery_app.task(bind=True, max_retries=get_settings().max_delivery_attempts - 1)
def process_order_task(self, order_id: str) -> dict:
    service = OrderFlowService(get_settings())
    try:
        order = service.process_order(order_id)
        return {"order_id": str(order.id), "status": order.status, "reference": order.transport_reference}
    except ConnectorDeliveryError as exc:
        logger.warning("Delivery failed for %s: %s", order_id, exc)
        raise self.retry(exc=exc, countdown=min(5 * (2 ** self.request.retries), 60))
