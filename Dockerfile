# Builds the CLI scanner image and records installed tool versions in /usr/share/vaptforge/tool-versions.txt.
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        ca-certificates \
        curl \
        dirb \
        git \
        gobuster \
        hydra \
        libio-socket-ssl-perl \
        libjson-perl \
        libnet-ssleay-perl \
        libxml-writer-perl \
        perl \
        sqlmap \
        whatweb \
    && git clone --depth 1 --branch 2.6.1 https://github.com/sullo/nikto.git /opt/nikto \
    && ln -s /opt/nikto/program/nikto.pl /usr/local/bin/nikto \
    && mkdir -p /usr/share/vaptforge /usr/share/wordlists/dirb /out \
    && test -s /usr/share/dirb/wordlists/common.txt \
    && ln -s /usr/share/dirb/wordlists/common.txt /usr/share/wordlists/dirb/common.txt \
    && dpkg-query -W -f='${binary:Package}=${Version}\n' \
        curl dirb gobuster hydra libio-socket-ssl-perl libjson-perl libnet-ssleay-perl libxml-writer-perl perl sqlmap whatweb \
        > /usr/share/vaptforge/tool-versions.txt \
    && printf 'nikto=2.6.1 (commit %s)\n' "$(git -C /opt/nikto rev-parse --short HEAD)" \
        >> /usr/share/vaptforge/tool-versions.txt \
    && apt-get purge --yes --auto-remove git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY vaptforge ./vaptforge

ARG VAPTFORGE_UID=1000
ARG VAPTFORGE_GID=1000
RUN groupadd --gid "${VAPTFORGE_GID}" vaptforge \
    && useradd --uid "${VAPTFORGE_UID}" --gid vaptforge --create-home --shell /usr/sbin/nologin vaptforge \
    && chown -R vaptforge:vaptforge /app /out

USER vaptforge
ENTRYPOINT ["python", "-m", "vaptforge.layer1.cli"]
