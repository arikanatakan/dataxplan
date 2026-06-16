import json
import pathlib

import pytest

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


@pytest.fixture
def load():
    def _load(name):
        return json.loads((FIXTURES / name).read_text())
    return _load
