import importlib
from importlib.metadata import version
import pytest
from uftr.environment import DEPENDENCIES


@pytest.mark.parametrize("distribution,module", DEPENDENCIES.items())
def test_required_dependency_really_imports(distribution, module):
    assert importlib.import_module(module) is not None
    assert version(distribution)
