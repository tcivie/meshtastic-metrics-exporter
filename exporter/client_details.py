from meshtastic.config_pb2 import Config
from meshtastic.mesh_pb2 import HardwareModel


class ClientDetails:
    def __init__(self, node_id, short_name='Unknown', long_name='Unknown', hardware_model=HardwareModel.UNSET,
                 role=None):
        self.node_id = node_id
        self.short_name = short_name
        self.long_name = long_name
        self.hardware_model: HardwareModel = hardware_model
        self.role: Config.DeviceConfig.Role = role

    def to_dict(self):
        return {
            'node_id': self.node_id,
            'short_name': self.short_name,
            'long_name': self.long_name,
            'hardware_model': self.get_hardware_model_name_from_code(self.hardware_model),
            'role': self.get_role_name_from_role(self.role)
        }

    @staticmethod
    def get_role_name_from_role(role):
        descriptor = Config.DeviceConfig.Role.DESCRIPTOR
        for enum_value in descriptor.values:
            if enum_value.number == role or enum_value.name == role:
                return enum_value.name
        return 'UNKNOWN_ROLE'

    @staticmethod
    def get_hardware_model_name_from_code(hardware_model):
        descriptor = HardwareModel.DESCRIPTOR
        for enum_value in descriptor.values:
            if enum_value.number == hardware_model or enum_value.name == hardware_model:
                return enum_value.name
        return 'UNKNOWN_HARDWARE_MODEL'
