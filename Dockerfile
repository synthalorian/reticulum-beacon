# ── Build stage: install runtime deps ────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

COPY pyproject.toml README.md ./
COPY src/ src/

# Build a wheel so we can install cleanly in the runtime stage
RUN pip install --upgrade pip build && \
    python -m build --wheel

# ── Runtime stage: minimal image ─────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Install runtime system dependencies (Reticulum needs none, but keep small)
RUN apt-get update && \
    apt-get install -y --no-install-recommends openssl ca-certificates curl && \
    rm -rf /var/lib/apt/lists/*

# Copy the wheel from builder and install
COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl

# Create non-root user
RUN groupadd --system beacon && \
    useradd --system --gid beacon --create-home beacon

# Data volume for configs, identities, certs, audit logs
VOLUME ["/etc/reticulum-beacon"]

# Expose default API port (matches beacon api start --port default)
EXPOSE 8931

USER beacon

ENTRYPOINT ["beacon"]
CMD ["api", "start"]
