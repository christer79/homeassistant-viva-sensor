import requests
import logging
import voluptuous as vol
from datetime import timedelta

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

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


def setup_platform(hass, config, add_entities, discovery_info=None):
    sensors_config = config.get(CONF_SENSORS)
    sensors = []
    for sensor_config in sensors_config:
        name = sensor_config[CONF_NAME]
        bbox = sensor_config[CONF_BBOX]
        scan_interval = sensor_config[CONF_SCAN_INTERVAL]
        sensor_manager = VivaSensorManager(name, bbox)
        sensors.append(VivaWindGustSensor(sensor_manager, scan_interval))
        sensors.append(VivaWindSpeedSensor(sensor_manager))
        sensors.append(VivaWindDirectionSensor(sensor_manager))
    add_entities(sensors, True)


class VivaSensorManager:
    def __init__(self, name, bbox):
        self._name = name
        self._bbox = bbox
        self._data = {}
        self.update()

    def update(self):
        url = f"https://geokatalog.sjofartsverket.se/mapservice/wms.axd/VindOchVatten?{self._bbox}"
        _LOGGER.info(f"Requesting {self._name}")
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            features = data.get("features", [])
            if features:
                feature = features[0]  # Assume we take the first feature
                properties = feature.get("properties", {})
                self._data = {
                    "gust_speed": properties.get("Byvind"),
                    "mean_speed": properties.get("Medelvind"),
                    "wind_direction": properties.get("Medelvind riktning"),
                    "gust_direction": properties.get("Byvind riktning"),
                    "station_id": properties.get("Stationsid"),
                    "station_name": properties.get("Namn"),
                    "gust_updated": properties.get("Byvind uppdaterad"),
                    "mean_updated": properties.get("Medelvind uppdaterad"),
                }
            else:
                _LOGGER.error("No features found in the response")
        else:
            _LOGGER.error(f"Failed to fetch data, status code: {response.status_code}")

    def get_data(self):
        return self._data


class VivaWindGustSensor(Entity):
    def __init__(self, manager, scan_interval):
        self._manager = manager
        self._name = f"{manager._name}_gust"
        self._state = None
        self._attributes = {}
        self.update = Throttle(timedelta(seconds=scan_interval))(self.update)

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._attributes

    def update(self):
        self._manager.update()
        data = self._manager.get_data()
        self._state = data.get("gust_speed")
        self._attributes = {
            "Stationsid": data.get("station_id"),
            "Namn": data.get("station_name"),
            "Byvind riktning": data.get("wind_direction"),
            "Byvind uppdaterad": data.get("gust_updated"),
        }


class VivaWindSpeedSensor(Entity):
    def __init__(self, manager):
        self._manager = manager
        self._name = f"{manager._name}_mean"
        self._state = None
        self._attributes = {}

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._attributes

    def update(self):
        data = self._manager.get_data()
        self._state = data.get("mean_speed")
        self._attributes = {
            "Stationsid": data.get("station_id"),
            "Namn": data.get("station_name"),
            "Medelvind riktning": data.get("wind_direction"),
            "Medelvind uppdaterad": data.get("mean_updated"),
        }


class VivaWindDirectionSensor(Entity):
    def __init__(self, manager):
        self._manager = manager
        self._name = f"{manager._name}_direction"
        self._state = None
        self._attributes = {}

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._attributes

    def update(self):
        data = self._manager.get_data()
        self._state = data.get("wind_direction")
        self._attributes = {
            "Stationsid": data.get("station_id"),
            "Namn": data.get("station_name"),
            "Byvind riktning": data.get("wind_direction"),
            "Medelvind riktning": data.get("wind_direction"),
            "Byvind uppdaterad": data.get("gust_updated"),
            "Medelvind uppdaterad": data.get("mean_updated"),
        }
