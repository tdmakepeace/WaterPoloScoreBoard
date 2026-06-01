"""Tests for results/temp output path helpers."""

from pathlib import Path

import start


def test_results_dirs_created():
    start.ensureResultsDirs()
    assert start.RESULTS_DIR.is_dir()
    assert start.TEMP_DIR.is_dir()


def test_temp_csv_path_is_under_results_temp():
    path = start.buildTempCsvPath()
    assert path.parent == start.TEMP_DIR
    assert path.name.startswith("temp-")
    assert path.suffix == ".csv"


def test_game_csv_path_is_under_results_temp():
    path = start.buildGameCsvPath()
    assert path.parent == start.TEMP_DIR
    assert path.suffix == ".csv"


def test_final_pdf_path_is_under_results():
    path = start.buildFinalPdfPath()
    assert path.parent == start.RESULTS_DIR
    assert path.suffix == ".pdf"
    assert "_END_" in path.stem
