from pathlib import Path

import cv2
import numpy as np

from app.analyzer import analyze_image


def test_analyzer_returns_expected_structure(tmp_path: Path):
    image = np.full((500, 500, 3), 120, dtype=np.uint8)
    path = tmp_path / "sample.jpg"

    assert cv2.imwrite(str(path), image)

    result = analyze_image(str(path))

    assert isinstance(result, dict)
    assert "image" in result
    assert "checks" in result
    assert "summary" in result
    assert "limitations" in result

    summary = result["summary"]

    assert summary["total_checks"] >= 4
    assert summary["evaluated_checks"] <= summary["total_checks"]

    assert 0.0 <= summary["confidence"] <= 1.0

    assert "checks_passed" in summary
    assert "checks_failed" in summary
    assert "checks_skipped" in summary
    assert "checks_unknown" in summary

    assert sum([
        summary["checks_passed"],
        summary["checks_failed"],
        summary["checks_skipped"],
        summary["checks_unknown"],
    ]) == summary["total_checks"]


def test_analyzer_reports_image_dimensions(tmp_path: Path):
    image = np.full((640, 480, 3), 120, dtype=np.uint8)
    path = tmp_path / "dimensions.jpg"

    assert cv2.imwrite(str(path), image)

    result = analyze_image(str(path))

    assert result["image"]["width"] == 480
    assert result["image"]["height"] == 640