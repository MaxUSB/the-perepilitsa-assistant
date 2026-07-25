FROM astral/uv:python3.14-bookworm

WORKDIR /opt/app

RUN apt-get update \
    && apt-get install --yes --no-install-recommends ffmpeg nodejs npm \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY src ./src
