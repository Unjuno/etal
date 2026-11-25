# Development-only G0 diagnostic; no model weights or external services.
# Base tag is not yet a frozen image digest. Do not use as confirmatory lock.
FROM python:3.12-slim@sha256:191083cdf6c7bda8c76158983163ead5d5cf7b77cf3033e805bb0f5296f51b4b
WORKDIR /app
ENV PYTHONPATH=/app/src PYTHONDONTWRITEBYTECODE=1
COPY src/ src/
COPY tests/ tests/
COPY protocols/ protocols/
COPY results/g0_grid.csv results/g0_grid.csv
COPY results/g01/grid.csv results/g01/grid.csv
COPY results/g01/codec_metrics.csv results/g01/codec_metrics.csv
COPY results/g01/summary.json results/g01/summary.json
COPY results/g01/representative_traces.json results/g01/representative_traces.json
USER 65534:65534
CMD ["python", "-m", "unittest", "discover", "-s", "tests", "-v"]
