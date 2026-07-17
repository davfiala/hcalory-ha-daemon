FROM ghcr.io/home-assistant/base:latest

ARG BUILD_VERSION=dev
ARG BUILD_ARCH=multiarch

LABEL \
  io.hass.name="HCalory BLE Daemon" \
  io.hass.description="Persistent BLE daemon for HCalory diesel heaters" \
  io.hass.version="${BUILD_VERSION}" \
  io.hass.type="addon" \
  io.hass.arch="${BUILD_ARCH}"

RUN apk add --no-cache \
    python3 \
    py3-pip \
    bluez \
    dbus

RUN python3 -m pip install --break-system-packages --no-cache-dir \
    "bleak<1.0.0" \
    "bleak-retry-connector<4.0" \
    "bluetooth-adapters<1.0.0"

COPY rootfs /
COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD ["/run.sh"]
