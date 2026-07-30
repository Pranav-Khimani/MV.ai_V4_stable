"""Offline checks for MV.ai's Windows volume fallback and error cleanup."""

from core.error_formatting import merge_error_messages
from tools.system.device_tools import DeviceTool


class ScalarEndpoint:
    def __init__(self):
        self.scalar = None

    def SetMasterVolumeLevelScalar(self, value, _event_context):
        self.scalar = value


class DecibelFallbackEndpoint:
    def __init__(self):
        self.target_db = None

    def SetMasterVolumeLevelScalar(self, _value, _event_context):
        raise OSError("simulated driver scalar rejection")

    def GetVolumeRange(self):
        return (-65.25, 0.0, 0.75)

    def SetMasterVolumeLevel(self, value, _event_context):
        self.target_db = value


def main() -> None:
    scalar = ScalarEndpoint()
    method = DeviceTool._set_endpoint_volume_percent(scalar, 50)
    assert method == "scalar"
    assert scalar.scalar == 0.5

    fallback = DecibelFallbackEndpoint()
    method = DeviceTool._set_endpoint_volume_percent(fallback, 100)
    assert method == "decibel"
    assert fallback.target_db == 0.0

    fallback_mid = DecibelFallbackEndpoint()
    method = DeviceTool._set_endpoint_volume_percent(fallback_mid, 50)
    assert method == "decibel"
    assert -65.25 < fallback_mid.target_db < 0.0

    message = merge_error_messages(
        "Task stopped at step 1: Device action failed: example",
        ["Device action failed: example"],
    )
    assert message == "Task stopped at step 1: Device action failed: example"

    tool = DeviceTool()
    assert tool.validate_percentage(100) == 100
    assert tool.validate_percentage("0") == 0
    assert tool.validate_percentage(101) is None

    print("[PASSED] Scalar volume method works.")
    print("[PASSED] 100% volume falls back to the endpoint dB maximum.")
    print("[PASSED] Duplicate task errors are collapsed.")
    print("[PASSED] Volume input validation works.")


if __name__ == "__main__":
    main()
