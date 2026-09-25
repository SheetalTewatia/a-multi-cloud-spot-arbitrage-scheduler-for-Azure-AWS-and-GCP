# Stage 1: build a virtualenv with Tide and its dependencies.
FROM python:3.14.7-slim-trixie AS build

ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /venv
ENV PATH="/venv/bin:$PATH"

WORKDIR /src
COPY pyproject.toml README.md ./
COPY tide ./tide
# pip is only needed to build; removing it drops its vendored libs from the scan surface.
RUN pip install . && pip uninstall -y pip

# Stage 2: small runtime image with just the virtualenv and migration files.
FROM python:3.14.7-slim-trixie

# Pull in Debian security fixes released after the base image was built,
# and remove the base image's pip (not needed at runtime).
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/* \
    && python -m pip uninstall -y pip

RUN useradd --create-home --uid 10001 tide
COPY --from=build /venv /venv
ENV PATH="/venv/bin:$PATH" PYTHONUNBUFFERED=1

WORKDIR /app
COPY alembic.ini ./
COPY alembic ./alembic

USER tide
EXPOSE 8000

# Apply migrations, then serve the API.
CMD ["sh", "-c", "alembic upgrade head && uvicorn tide.api.main:app --host 0.0.0.0 --port 8000"]
