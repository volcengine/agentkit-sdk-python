# Copyright (c) 2026 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Public export guards for the ``agentkit.apps`` package.

Target: ``agentkit/apps/__init__.py``. The package exports its four app
classes through a *lazy* module-level ``__getattr__`` (one ``if`` branch per
name) rather than eager imports, so a typo in a branch -- or a branch/`
``__all__`` mismatch -- would not fail at import time and could ship
silently. These tests resolve every advertised name through the real lazy
path and pin ``__all__`` to the documented public surface.
"""

from __future__ import annotations

import inspect

import pytest

import agentkit.apps

# The four app classes the package documents as its public surface.
_DOCUMENTED_APP_CLASSES = {
    "AgentkitA2aApp",
    "AgentkitMCPApp",
    "AgentkitSimpleApp",
    "AgentkitAgentServerApp",
}


def test_all_matches_the_documented_app_classes():
    assert set(agentkit.apps.__all__) == _DOCUMENTED_APP_CLASSES
    # No duplicate entries hiding in the list form.
    assert len(agentkit.apps.__all__) == len(set(agentkit.apps.__all__))


@pytest.mark.parametrize("name", sorted(_DOCUMENTED_APP_CLASSES))
def test_every_export_resolves_through_the_lazy_getattr_to_a_class(name):
    # getattr() on the module exercises the real lazy __getattr__ branch.
    obj = getattr(agentkit.apps, name)

    assert inspect.isclass(obj), f"{name} did not resolve to a class"
    # The branch must return the class it advertises, not a lookalike.
    assert obj.__name__ == name
    assert obj.__module__.startswith("agentkit.apps.")


def test_unknown_attribute_raises_attribute_error():
    # The lazy __getattr__ fallthrough must raise AttributeError (not return
    # None or raise something else), so hasattr()/import-from behave normally.
    with pytest.raises(AttributeError, match="has no attribute 'NotAnApp'"):
        getattr(agentkit.apps, "NotAnApp")
