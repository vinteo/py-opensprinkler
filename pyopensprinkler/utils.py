"""Commonly used functions."""


def _is_new_feature_supported(controller, required_version, required_minor_version):
    """Compare current firmware version with the first supported version of a feature"""
    firmware_version = controller.firmware_version
    firmware_minor_version = controller.firmware_minor_version
    if firmware_version > required_version:
        return True
    elif firmware_version == required_version:
        return firmware_minor_version >= required_minor_version
    else:
        return False


def _is_removed_feature_supported(
    controller, last_supported_version, last_supported_minor_version
):
    """Compare current firmware version with the last supported version of a feature"""
    firmware_version = controller.firmware_version
    firmware_minor_version = controller.firmware_minor_version
    if firmware_version < last_supported_version:
        return True
    elif firmware_version == last_supported_version:
        return firmware_minor_version <= last_supported_minor_version
    else:
        return False
