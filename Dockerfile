
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY requirements.txt .

RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install \
    --index-url https://pypi.tuna.tsinghua.edu.cn/simple/ \
    --retries 3 \
    --timeout 60 \
    -r requirements.txt

# Keep only headless OpenCV for server-side processing
RUN python -m pip uninstall -y opencv-python && \
    python -m pip install \
    --index-url https://pypi.tuna.tsinghua.edu.cn/simple/ \
    --no-deps --force-reinstall \
    opencv-python-headless==4.11.0.86

COPY . .

RUN mkdir -p /app/data/uploads

EXPOSE 8000
