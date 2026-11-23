# This file is part of a software collection for data acquisition (matr1x).
# Copyright (C) 2006-2026 matr1x developers
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""Tests for the deprecation notifications of legacy access paths."""

import logging

import pytest

from matr1x.core import deprecation
from matr1x.core.models import Message as CanonicalMessage


@pytest.fixture
def notifier():
    """Collect messages passed to the registered GUI callback."""
    messages: list[str] = []
    deprecation.set_deprecation_notifier(messages.append)
    yield messages
    deprecation.set_deprecation_notifier(None)


def test_notify_deprecated_access_reports_once(notifier, caplog):
    """A legacy path is reported once per process, to log and callback."""
    with caplog.at_level(logging.WARNING, logger="matr1x.core.deprecation"):
        deprecation.notify_deprecated_access("a.b", "c.d")
        deprecation.notify_deprecated_access("a.b", "c.d")
    assert notifier == ["a.b is deprecated and will be removed in v8.8.0; use c.d instead."]
    assert caplog.text.count("[MATR1X_DEPRECATED]") == 1
    assert "use c.d instead" in caplog.text


def test_shim_returns_canonical_object():
    """The deprecated shim path provides the canonical object."""
    from matr1x.models import Message

    assert Message is CanonicalMessage


def test_shim_unknown_name_raises_attribute_error():
    """Accessing a name the shim does not provide fails as usual."""
    import matr1x.models

    with pytest.raises(AttributeError):
        _ = matr1x.models.DoesNotExist
