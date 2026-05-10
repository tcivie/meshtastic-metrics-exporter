"""Pure unit tests for `exporter.client_details.ClientDetails`."""

import pytest

try:
    from exporter.client_details import ClientDetails
    from meshtastic.config_pb2 import Config
except ImportError:
    try:
        from exporter.client_details import ClientDetails
        from meshtastic.protobuf.config_pb2 import Config
    except ImportError:
        pytest.skip("meshtastic protobuf not installed", allow_module_level=True)


class TestClientDetails:
    def test_unknown_role_falls_back_to_default(self):
        assert ClientDetails.get_role_name_from_role(99999) == "UNKNOWN_ROLE"

    def test_unknown_hardware_falls_back_to_default(self):
        assert (
            ClientDetails.get_hardware_model_name_from_code(99999)
            == "UNKNOWN_HARDWARE_MODEL"
        )

    def test_role_round_trip_by_name(self):
        for v in Config.DeviceConfig.Role.DESCRIPTOR.values:
            assert ClientDetails.get_role_name_from_role(v.number) == v.name

    def test_default_constructor_uses_unknown_labels(self):
        cd = ClientDetails(node_id="42")
        assert cd.short_name == "Unknown"
        assert cd.long_name == "Unknown"
        assert cd.node_id == "42"

    def test_to_dict_contains_expected_keys(self):
        cd = ClientDetails(node_id="42")
        d = cd.to_dict()
        assert set(d) == {
            "node_id",
            "short_name",
            "long_name",
            "hardware_model",
            "role",
        }
