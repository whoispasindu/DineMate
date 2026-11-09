import sys

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("ultralytics")

from vision.nms import install_torch_nms  # noqa: E402


def test_stand_in_nms_keeps_the_best_of_overlapping_boxes() -> None:
    saved = {k: v for k, v in sys.modules.items() if k == "torchvision" or k.startswith("torchvision.")}
    try:
        install_torch_nms()
        import torchvision

        boxes = torch.tensor([[0, 0, 10, 10], [1, 1, 10, 10], [50, 50, 60, 60]], dtype=torch.float32)
        scores = torch.tensor([0.9, 0.8, 0.7])
        assert torchvision.ops.nms(boxes, scores, 0.5).tolist() == [0, 2]
    finally:
        for name in [k for k in sys.modules if k == "torchvision" or k.startswith("torchvision.")]:
            sys.modules.pop(name)
        sys.modules.update(saved)
