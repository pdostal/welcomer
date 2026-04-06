FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder
WORKDIR /build
COPY . .
RUN uv build --wheel

# checkov:skip=CKV_DOCKER_2:CLI tool - HEALTHCHECK not applicable
FROM python:3.14-slim
COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl \
    && useradd --no-create-home --shell /bin/false welcomer
USER welcomer
ENTRYPOINT ["welcomer"]
