FROM denoland/deno:bin-2.5.6 AS deno

FROM astral/uv:python3.14-bookworm

WORKDIR /opt/app

RUN apt-get update \
    && apt-get install --yes --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY --from=deno /deno /usr/local/bin/deno

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY src ./src
