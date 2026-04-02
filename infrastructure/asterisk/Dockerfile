FROM andrius/asterisk:22

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends gettext-base libvorbisenc2 \
    && rm -rf /var/lib/apt/lists/*

COPY infrastructure/asterisk/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

RUN mkdir -p /templates
COPY infrastructure/asterisk/config/pjsip.conf.template /templates/pjsip.conf.template

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
