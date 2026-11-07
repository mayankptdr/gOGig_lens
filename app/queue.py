from redis import Redis
from rq import Queue, Retry
from app.config import settings

redis_connection = Redis.from_url(settings.redis_url)
image_queue = Queue("image-processing", connection=redis_connection, default_timeout=300)

def enqueue_image(image_id: str):
    from app.worker import process_image
    return image_queue.enqueue(
        process_image,
        image_id,
        job_timeout=300,
        retry=Retry(max=2, interval=[10, 30]),
        result_ttl=86400,
        failure_ttl=604800,
    )
