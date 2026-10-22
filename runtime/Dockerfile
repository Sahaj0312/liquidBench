FROM node:22.16.0-bookworm-slim@sha256:048ed02c5fd52e86fda6fbd2f6a76cf0d4492fd6c6fee9e2c463ed5108da0e34 AS node
WORKDIR /opt/liquidbench
COPY runtime/package*.json ./
RUN npm ci --omit=dev --ignore-scripts

FROM ruby:3.3.8-slim-bookworm@sha256:307aed56240959e9cd3fcc10740ae8d0e6c461e9b42efc076100d4f8126b87b9
RUN apt-get update && apt-get install -y --no-install-recommends python3 libstdc++6 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 1000 --create-home agent
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /opt/liquidbench/node_modules /opt/liquidbench/node_modules
WORKDIR /opt/liquidbench
COPY runtime/Gemfile runtime/Gemfile.lock ./
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && gem install bundler -v 2.6.2 --no-document \
    && bundle config set frozen true && bundle install \
    && apt-get purge -y --auto-remove build-essential \
    && rm -rf /var/lib/apt/lists/*
COPY runtime/ ./
WORKDIR /workspace
USER 1000:1000
CMD ["sleep", "infinity"]
