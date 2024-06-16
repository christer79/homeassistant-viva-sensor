import requests
import logging
import voluptuous as vol
from datetime import timedelta

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Viva Sensor"
CONF_SENSORS = "sensors"
CONF_BBOX = "bbox"
CONF_NAME = "name"
CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_SCAN_INTERVAL = 600

SENSOR_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_BBOX): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.Number,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_SENSORS): vol.All(cv.ensure_list, [SENSOR_SCHEMA]),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):  # noqa: D103
    sensors_config = config.get(CONF_SENSORS)
    sensors = []
    for sensor_config in sensors_config:
        name = sensor_config[CONF_NAME]
        bbox = sensor_config[CONF_BBOX]
        scan_interval = sensor_config[CONF_SCAN_INTERVAL]
        sensors.append(VivaSensor(name, bbox, scan_interval))
    add_entities(sensors, True)


class VivaSensor(Entity):  # noqa: D101
    def __init__(self, name, bbox, scan_interval):  # noqa: D107
        self._name = name
        self._state = None
        self._attributes = {}
        self._bbox = bbox
        self.update = Throttle(timedelta(seconds=scan_interval))(self.update)

    @property
    def name(self):  # noqa: D102
        return self._name

    @property
    def state(self):  # noqa: D102
        return self._state

    @property
    def extra_state_attributes(self):  # noqa: D102
        return self._attributes

    def update(self):  # noqa: D102
        url = f"https://geokatalog.sjofartsverket.se/mapservice/wms.axd/VindOchVatten?{self._bbox}"
        _LOGGER.info(url)
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            features = data.get("features", [])
            if features:
                feature = features[0]  # Assume we take the first feature
                properties = feature.get("properties", {})
                self._state = properties.get("Medelvind")
                _LOGGER.info(f"Fetched {properties.get("Namn")}")
                self._attributes = {
                    "Stationsid": properties.get("Stationsid"),
                    "Namn": properties.get("Namn"),
                    "Byvind": properties.get("Byvind"),
                    "Byvind riktning": properties.get("Byvind riktning"),
                    "Medelvind": properties.get("Medelvind"),
                    "Medelvind riktning": properties.get("Medelvind riktning"),
                    "Byvind uppdaterad": properties.get("Byvind uppdaterad"),
                    "Medelvind uppdaterad": properties.get("Medelvind uppdaterad"),
                }
            else:
                _LOGGER.error("No features found in the response")
        else:
            _LOGGER.error(f"Failed to fetch data, status code: {response.status_code}")
