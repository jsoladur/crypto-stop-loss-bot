FROM python:3.13.5-slim-bullseye as base
WORKDIR /app
ENV \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONHASHSEED=random \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1

# Install bash for connecting via TTY
RUN apt-get update && apt-get install -y --no-install-recommends \
        bash \
        sqlite3 \
        && rm -rf /var/lib/apt/lists/*
# ==================================================================
FROM base as build
WORKDIR /app

ARG UV_VERSION=0.6.14

ENV \
    PIP_DEFAULT_TIMEOUT=100 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_VERSION=$UV_VERSION \
    UV_INSTALL_DIR="/opt/uv"

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        gcc \
        python3-dev \
        && rm -rf /var/lib/apt/lists/*

# Download the latest installer
ADD https://astral.sh/uv/$UV_VERSION/install.sh /uv-installer.sh

# Run the installer then remove it
RUN sh /uv-installer.sh && rm /uv-installer.sh

ENV PATH="$UV_INSTALL_DIR:$PATH"

COPY /uv.lock /pyproject.toml ./

# Install only the production dependencies
RUN uv sync --frozen --no-dev --no-install-project

COPY  /src/ ./src/
COPY  ./*.md ./

# Install project
RUN uv sync --frozen --no-dev
# ==================================================================
FROM base as production

# Create user with the name jmsoladev
RUN groupadd -g 1001 jmsoladev && \
    useradd -m -u 1001 -g jmsoladev jmsoladev

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

COPY --from=build --chown=jmsoladev:jmsoladev ./app /app

USER jmsoladev
WORKDIR /app

EXPOSE 8000
ENTRYPOINT /docker-entrypoint.sh $0 $@
CMD ["uvicorn", "crypto_trailing_stop.main:main", "--host", "0.0.0.0", "--port", "8000", "--loop", "asyncio"]