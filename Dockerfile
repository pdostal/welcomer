FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder
WORKDIR /build
COPY . .
RUN uv build --wheel

FROM python:3.14-slim
COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl
ENTRYPOINT ["welcomer"]
