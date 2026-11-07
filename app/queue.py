
from redis import Redis
from rq import Queue

from app.config import settings


redis_connection = Redis.from_url(
    settings.redis_url,
    socket_connect_timeout=5,
    socket_timeout=5,
)

image_queue = Queue(
    name="image-processing",
    connection=redis_connection,
    default_timeout=settings.job_timeout_seconds,
)


def enqueue_image(image_id: str, delay: int = 0):
    from app.worker import process_image

    return image_queue.enqueue_in(
        __import__("datetime").timedelta(seconds=delay),
        process_image,
        image_id,
        job_timeout=settings.job_timeout_seconds,
        result_ttl=86400,
        failure_ttl=604800,
    ) if delay > 0 else image_queue.enqueue(
        process_image,
        image_id,
        job_timeout=settings.job_timeout_seconds,
        result_ttl=86400,
        failure_ttl=604800,
    )
