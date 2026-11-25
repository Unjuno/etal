# Development-only G0 diagnostic; no model weights or external services.
# Base tag is not yet a frozen image digest. Do not use as confirmatory lock.
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONPATH=/app/src PYTHONDONTWRITEBYTECODE=1
COPY src/ src/
COPY tests/ tests/
COPY results/g0_grid.csv results/g0_grid.csv
USER 65534:65534
CMD ["python", "-m", "unittest", "discover", "-s", "tests", "-v"]
