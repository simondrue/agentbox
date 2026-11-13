FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       squid ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

USER proxy

HEALTHCHECK --interval=5s --timeout=3s --start-period=10s \
  CMD curl --silent --show-error --max-time 2 \
      --output /dev/null \
      --proxy http://127.0.0.1:3128 \
      http://proxy-health.invalid/ || exit 1

CMD ["squid", "-N", "-f", "/etc/squid/squid.conf"]
