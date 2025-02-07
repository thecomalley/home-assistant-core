"""Support for August doorbell camera."""

from __future__ import annotations

import logging

from aiohttp import ClientSession
from yalexs.activity import ActivityType
from yalexs.doorbell import Doorbell
from yalexs.util import update_doorbell_image_from_activity

from homeassistant.components.camera import Camera
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AugustConfigEntry, AugustData
from .const import DEFAULT_NAME, DEFAULT_TIMEOUT
from .entity import AugustEntityMixin

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AugustConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up August cameras."""
    data = config_entry.runtime_data
    # Create an aiohttp session instead of using the default one since the
    # default one is likely to trigger august's WAF if another integration
    # is also using Cloudflare
    session = aiohttp_client.async_create_clientsession(hass)
    async_add_entities(
        AugustCamera(data, doorbell, session, DEFAULT_TIMEOUT)
        for doorbell in data.doorbells
    )


class AugustCamera(AugustEntityMixin, Camera):
    """An implementation of an August security camera."""

    _attr_translation_key = "camera"
    _attr_motion_detection_enabled = True
    _attr_brand = DEFAULT_NAME
    _image_url: str | None = None
    _image_content: bytes | None = None

    def __init__(
        self, data: AugustData, device: Doorbell, session: ClientSession, timeout: int
    ) -> None:
        """Initialize an August security camera."""
        super().__init__(data, device, "camera")
        self._timeout = timeout
        self._session = session

    @property
    def is_recording(self) -> bool:
        """Return true if the device is recording."""
        return self._device.has_subscription

    @property
    def model(self) -> str | None:
        """Return the camera model."""
        return self._detail.model

    async def _async_update(self):
        """Update device."""
        _LOGGER.debug("async_update called %s", self._detail.device_name)
        await self._data.refresh_camera_by_id(self._device_id)
        self._update_from_data()

    @callback
    def _update_from_data(self) -> None:
        """Get the latest state of the sensor."""
        doorbell_activity = self._data.activity_stream.get_latest_device_activity(
            self._device_id,
            {ActivityType.DOORBELL_MOTION, ActivityType.DOORBELL_IMAGE_CAPTURE},
        )
        if doorbell_activity is not None:
            update_doorbell_image_from_activity(self._detail, doorbell_activity)

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return bytes of camera image."""
        self._update_from_data()

        if self._image_url is not self._detail.image_url:
            self._image_content = await self._data.async_get_doorbell_image(
                self._device_id, self._session, timeout=self._timeout
            )
            self._image_url = self._detail.image_url

        return self._image_content
