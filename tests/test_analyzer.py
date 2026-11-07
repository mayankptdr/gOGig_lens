from pathlib import Path
import cv2
import numpy as np
from app.analyzer import analyze_image

def test_analyzer_returns_expected_structure(tmp_path: Path):
    image = np.full((500, 500, 3), 120, dtype=np.uint8)
    path = tmp_path / "sample.jpg"
    assert cv2.imwrite(str(path), image)
    result = analyze_image(str(path))
    assert "checks" in result
    assert "summary" in result
    assert result["summary"]["checks_total"] >= 4
