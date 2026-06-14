import sys
import pytest
from unittest.mock import MagicMock
from PyQt5.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


@pytest.fixture
def mock_controller():
    ctrl = MagicMock()
    ctrl.detect.return_value = [1, 2, 3]
    ctrl.read_limit.return_value = False
    return ctrl
