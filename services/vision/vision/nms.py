import logging
import sys
import types

log = logging.getLogger("dinemate.vision.nms")


def _drop_partial_import() -> None:
    for name in [n for n in sys.modules if n == "torchvision" or n.startswith("torchvision.")]:
        sys.modules.pop(name, None)


def install_torch_nms() -> None:
    from ultralytics.utils.nms import TorchNMS

    _drop_partial_import()
    ops = types.ModuleType("torchvision.ops")
    ops.nms = TorchNMS.nms  # type: ignore[attr-defined]
    module = types.ModuleType("torchvision")
    module.ops = ops  # type: ignore[attr-defined]
    module.__version__ = "0.0.0+dinemate-nms"  # type: ignore[attr-defined]
    sys.modules["torchvision"] = module
    sys.modules["torchvision.ops"] = ops


def ensure_nms() -> bool:
    try:
        import torchvision  # noqa: F401
    except (ImportError, OSError, RuntimeError) as exc:
        log.warning(
            "torchvision could not load (%s); using the pure PyTorch NMS from ultralytics instead. "
            "On Windows this is usually Smart App Control blocking torchvision's compiled extension.",
            exc.__class__.__name__,
        )
        install_torch_nms()
        return False
    return True
