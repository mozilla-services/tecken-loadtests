FROM python:3.11-slim

# Set user and group
ARG groupid=10001
ARG userid=10001

WORKDIR /app/
RUN groupadd --gid $groupid app && \
    useradd -g app --uid $userid --shell /usr/sbin/nologin --create-home app

# deps
RUN DEBIAN_FRONTEND=noninteractive apt-get -y update && apt-get -y upgrade

COPY requirements.txt /app/requirements.txt
RUN pip install -U 'pip>=8' && \
    pip install --no-cache-dir -r /app/requirements.txt

ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONPATH /app

USER app

# shell
CMD /bin/bash
