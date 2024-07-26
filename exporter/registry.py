import geopy.point
from geopy.geocoders import Nominatim
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

from exporter.client_details import ClientDetails
from exporter.db_handler import DBHandler


class _Metrics:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(_Metrics, cls).__new__(cls)
        return cls._instance

    def __init__(self, registry: CollectorRegistry, db: DBHandler):
        if not hasattr(self, 'initialized'):  # Ensuring __init__ runs only once
            self._registry = registry
            self._init_metrics()
            self.initialized = True  # Attribute to indicate initialization
            self.geolocator = Nominatim()
            self.db = db

    @staticmethod
    def _get_common_labels():
        return [
            'node_id', 'short_name', 'long_name', 'hardware_model', 'role'
        ]

    def _init_metrics(self):
        self._init_metrics_text_message()
        self._init_metrics_telemetry_device()
        self._init_metrics_telemetry_environment()
        self._init_metrics_telemetry_air_quality()
        self._init_metrics_telemetry_power()
        self._init_route_discovery_metrics()

    def _init_metrics_text_message(self):
        self.message_length_histogram = Histogram(
            'text_message_app_length',
            'Length of text messages processed by the app',
            self._get_common_labels(),
            registry=self._registry
        )

    def update_metrics_position(self, latitude, longitude, altitude, precision, client_details: ClientDetails):
        point = geopy.point.Point(latitude, longitude, altitude)
        location = self.geolocator.reverse(point, language='en')

        country = location.raw.get('address', {}).get('country', 'Unknown')
        city = location.raw.get('address', {}).get('city', 'Unknown')
        state = location.raw.get('address', {}).get('state', 'Unknown')

        def db_operation(cur, conn):
            cur.execute("""
            UPDATE node_details
            SET latitude = %s, longitude = %s, altitude = %s, precision = %s, country = %s, city = %s, state = %s
            WHERE node_id = %s
            """, (latitude, longitude, altitude, precision, country, city, state, client_details.node_id))
            conn.commit()

        self.db.execute_db_operation(db_operation)

    def _init_metrics_telemetry_power(self):
        self.ch1_voltage_gauge = Gauge(
            'telemetry_app_ch1_voltage',
            'Voltage measured by the device on channel 1',
            self._get_common_labels(),
            registry=self._registry
        )

        self.ch1_current_gauge = Gauge(
            'telemetry_app_ch1_current',
            'Current measured by the device on channel 1',
            self._get_common_labels(),
            registry=self._registry
        )

        self.ch2_voltage_gauge = Gauge(
            'telemetry_app_ch2_voltage',
            'Voltage measured by the device on channel 2',
            self._get_common_labels(),
            registry=self._registry
        )

        self.ch2_current_gauge = Gauge(
            'telemetry_app_ch2_current',
            'Current measured by the device on channel 2',
            self._get_common_labels(),
            registry=self._registry
        )

        self.ch3_voltage_gauge = Gauge(
            'telemetry_app_ch3_voltage',
            'Voltage measured by the device on channel 3',
            self._get_common_labels(),
            registry=self._registry
        )

        self.ch3_current_gauge = Gauge(
            'telemetry_app_ch3_current',
            'Current measured by the device on channel 3',
            self._get_common_labels(),
            registry=self._registry
        )

    def _init_metrics_telemetry_air_quality(self):
        self.pm10_standard_gauge = Gauge(
            'telemetry_app_pm10_standard',
            'Concentration Units Standard PM1.0',
            self._get_common_labels(),
            registry=self._registry
        )

        self.pm25_standard_gauge = Gauge(
            'telemetry_app_pm25_standard',
            'Concentration Units Standard PM2.5',
            self._get_common_labels(),
            registry=self._registry
        )

        self.pm100_standard_gauge = Gauge(
            'telemetry_app_pm100_standard',
            'Concentration Units Standard PM10.0',
            self._get_common_labels(),
            registry=self._registry
        )

        self.pm10_environmental_gauge = Gauge(
            'telemetry_app_pm10_environmental',
            'Concentration Units Environmental PM1.0',
            self._get_common_labels(),
            registry=self._registry
        )

        self.pm25_environmental_gauge = Gauge(
            'telemetry_app_pm25_environmental',
            'Concentration Units Environmental PM2.5',
            self._get_common_labels(),
            registry=self._registry
        )

        self.pm100_environmental_gauge = Gauge(
            'telemetry_app_pm100_environmental',
            'Concentration Units Environmental PM10.0',
            self._get_common_labels(),
            registry=self._registry
        )

        self.particles_03um_gauge = Gauge(
            'telemetry_app_particles_03um',
            '0.3um Particle Count',
            self._get_common_labels(),
            registry=self._registry
        )

        self.particles_05um_gauge = Gauge(
            'telemetry_app_particles_05um',
            '0.5um Particle Count',
            self._get_common_labels(),
            registry=self._registry
        )

        self.particles_10um_gauge = Gauge(
            'telemetry_app_particles_10um',
            '1.0um Particle Count',
            self._get_common_labels(),
            registry=self._registry
        )

        self.particles_25um_gauge = Gauge(
            'telemetry_app_particles_25um',
            '2.5um Particle Count',
            self._get_common_labels(),
            registry=self._registry
        )

        self.particles_50um_gauge = Gauge(
            'telemetry_app_particles_50um',
            '5.0um Particle Count',
            self._get_common_labels(),
            registry=self._registry
        )

        self.particles_100um_gauge = Gauge(
            'telemetry_app_particles_100um',
            '10.0um Particle Count',
            self._get_common_labels(),
            registry=self._registry
        )

    def _init_metrics_telemetry_environment(self):
        # Define gauges for environment metrics
        self.temperature_gauge = Gauge(
            'telemetry_app_temperature',
            'Temperature measured by the device',
            self._get_common_labels(),
            registry=self._registry
        )

        self.relative_humidity_gauge = Gauge(
            'telemetry_app_relative_humidity',
            'Relative humidity percent measured by the device',
            self._get_common_labels(),
            registry=self._registry
        )

        self.barometric_pressure_gauge = Gauge(
            'telemetry_app_barometric_pressure',
            'Barometric pressure in hPA measured by the device',
            self._get_common_labels(),
            registry=self._registry
        )

        self.gas_resistance_gauge = Gauge(
            'telemetry_app_gas_resistance',
            'Gas resistance in MOhm measured by the device',
            self._get_common_labels(),
            registry=self._registry
        )

        self.iaq_gauge = Gauge(
            'telemetry_app_iaq',
            'IAQ value measured by the device (0-500)',
            self._get_common_labels(),
            registry=self._registry
        )

        self.distance_gauge = Gauge(
            'telemetry_app_distance',
            'Distance measured by the device in mm',
            self._get_common_labels(),
            registry=self._registry
        )

        self.lux_gauge = Gauge(
            'telemetry_app_lux',
            'Ambient light measured by the device in Lux',
            self._get_common_labels(),
            registry=self._registry
        )

        self.white_lux_gauge = Gauge(
            'telemetry_app_white_lux',
            'White light measured by the device in Lux',
            self._get_common_labels(),
            registry=self._registry
        )

        self.ir_lux_gauge = Gauge(
            'telemetry_app_ir_lux',
            'Infrared light measured by the device in Lux',
            self._get_common_labels(),
            registry=self._registry
        )

        self.uv_lux_gauge = Gauge(
            'telemetry_app_uv_lux',
            'Ultraviolet light measured by the device in Lux',
            self._get_common_labels(),
            registry=self._registry
        )

        self.wind_direction_gauge = Gauge(
            'telemetry_app_wind_direction',
            'Wind direction in degrees measured by the device',
            self._get_common_labels(),
            registry=self._registry
        )

        self.wind_speed_gauge = Gauge(
            'telemetry_app_wind_speed',
            'Wind speed in m/s measured by the device',
            self._get_common_labels(),
            registry=self._registry
        )

        self.weight_gauge = Gauge(
            'telemetry_app_weight',
            'Weight in KG measured by the device',
            self._get_common_labels(),
            registry=self._registry
        )

    def _init_metrics_telemetry_device(self):
        self.battery_level_gauge = Gauge(
            'telemetry_app_battery_level',
            'Battery level of the device (0-100, >100 means powered)',
            self._get_common_labels(),
            registry=self._registry
        )

        self.voltage_gauge = Gauge(
            'telemetry_app_voltage',
            'Voltage measured by the device',
            self._get_common_labels(),
            registry=self._registry
        )

        # Define gauges for channel utilization and air utilization for TX
        self.channel_utilization_gauge = Gauge(
            'telemetry_app_channel_utilization',
            'Utilization for the current channel, including well-formed TX, RX, and noise',
            self._get_common_labels(),
            registry=self._registry
        )

        self.air_util_tx_gauge = Gauge(
            'telemetry_app_air_util_tx',
            'Percent of airtime for transmission used within the last hour',
            self._get_common_labels(),
            registry=self._registry
        )

        # Define a counter for uptime in seconds
        self.uptime_seconds_counter = Counter(
            'telemetry_app_uptime_seconds',
            'How long the device has been running since the last reboot (in seconds)',
            self._get_common_labels(),
            registry=self._registry
        )

    def _init_route_discovery_metrics(self):
        self.route_discovery_gauge = Gauge(
            'route_length',
            'Number of nodes in the route',
            self._get_common_labels(),
            registry=self._registry
        )
        self.route_discovery_response_counter = Counter(
            'route_response',
            'Number of responses to route discovery',
            self._get_common_labels() + ['response_type'],
            registry=self._registry
        )
