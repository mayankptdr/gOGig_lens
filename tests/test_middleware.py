
import asyncio

from app.main import UploadBodyLimitMiddleware


async def run_middleware(
    body_chunks,
    headers=None,
    path="/api/v1/images/upload",
    max_bytes=10,
):
    sent_messages = []
    chunks = iter(body_chunks)

    async def receive():
        try:
            body = next(chunks)
            return {
                "type": "http.request",
                "body": body,
                "more_body": bool(list_copy := []),
            }
        except StopIteration:
            return {
                "type": "http.request",
                "body": b"",
                "more_body": False,
            }

    # Build explicit request messages for reliable streaming tests.
    messages = [
        {
            "type": "http.request",
            "body": chunk,
            "more_body": index < len(body_chunks) - 1,
        }
        for index, chunk in enumerate(body_chunks)
    ]

    message_index = 0

    async def controlled_receive():
        nonlocal message_index

        if message_index < len(messages):
            message = messages[message_index]
            message_index += 1
            return message

        return {
            "type": "http.request",
            "body": b"",
            "more_body": False,
        }

    async def send(message):
        sent_messages.append(message)

    async def downstream_app(scope, receive, send):
        while True:
            message = await receive()

            if message["type"] == "http.request":
                if not message.get("more_body", False):
                    break

        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [],
        })
        await send({
            "type": "http.response.body",
            "body": b"OK",
        })

    scope = {
        "type": "http",
        "method": "POST",
        "path": path,
        "headers": headers or [],
    }

    middleware = UploadBodyLimitMiddleware(
        downstream_app,
        max_bytes=max_bytes,
    )

    await middleware(scope, controlled_receive, send)

    return sent_messages


def get_response_status(messages):
    for message in messages:
        if message["type"] == "http.response.start":
            return message["status"]

    return None


def test_rejects_oversized_content_length():
    messages = asyncio.run(
        run_middleware(
            body_chunks=[],
            headers=[(b"content-length", b"100")],
            max_bytes=10,
        )
    )

    assert get_response_status(messages) == 413


def test_rejects_oversized_stream_without_content_length():
    messages = asyncio.run(
        run_middleware(
            body_chunks=[b"123456", b"789012"],
            headers=[],
            max_bytes=10,
        )
    )

    assert get_response_status(messages) == 413


def test_accepts_request_within_body_limit():
    messages = asyncio.run(
        run_middleware(
            body_chunks=[b"12345", b"67890"],
            headers=[],
            max_bytes=10,
        )
    )

    assert get_response_status(messages) == 200


def test_non_upload_endpoint_is_not_affected():
    messages = asyncio.run(
        run_middleware(
            body_chunks=[b"123456789012345"],
            headers=[],
            path="/health",
            max_bytes=10,
        )
    )

    assert get_response_status(messages) == 200
