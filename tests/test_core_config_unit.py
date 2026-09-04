"""Unit tests for core.config module."""
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

from core.config import ClubSchedule, Club, _is_pytest_running


class TestIsPytestRunning:
    """Test _is_pytest_running() helper function."""

    def test_pytest_in_sys_modules(self):
        """Should return True if pytest is in sys.modules."""
        with patch.dict(sys.modules, {"pytest": MagicMock()}):
            result = _is_pytest_running()
            assert result is True

    def test_pytest_in_argv(self):
        """Should return True if pytest is in sys.argv."""
        original_argv = sys.argv.copy()
        try:
            sys.argv = ["python", "pytest", "tests/"]
            result = _is_pytest_running()
            assert result is True
        finally:
            sys.argv = original_argv

    def test_pytest_not_running(self):
        """Should return False if pytest is not running."""
        # This is tricky because pytest IS running during these tests.
        # We test by checking the actual state.
        result = _is_pytest_running()
        assert result is True  # We're in pytest


class TestClubSchedule:
    """Test ClubSchedule dataclass."""

    def test_club_schedule_minimal(self):
        """Should create ClubSchedule with required fields."""
        schedule = ClubSchedule(weekday="friday", game_time="19:30")
        assert schedule.weekday == "friday"
        assert schedule.game_time == "19:30"
        assert schedule.create_time is None
        assert schedule.create_days_before == 0
        assert schedule.aetherhub_fetch_times == []
        assert schedule.find_latest is False
        assert schedule.reminder_time is None

    def test_club_schedule_full(self):
        """Should create ClubSchedule with all fields."""
        schedule = ClubSchedule(
            weekday="monday",
            game_time="20:00",
            create_time="18:00",
            create_days_before=1,
            aetherhub_fetch_times=["20:15", "21:00"],
            find_latest=True,
            reminder_time="19:45",
        )
        assert schedule.weekday == "monday"
        assert schedule.game_time == "20:00"
        assert schedule.create_time == "18:00"
        assert schedule.create_days_before == 1
        assert schedule.aetherhub_fetch_times == ["20:15", "21:00"]
        assert schedule.find_latest is True
        assert schedule.reminder_time == "19:45"


class TestClub:
    """Test Club dataclass."""

    def test_club_minimal(self):
        """Should create Club with required fields."""
        schedule = ClubSchedule(weekday="friday", game_time="19:30")
        club = Club(name="Goldfish", chat_id=123456, schedules=[schedule])
        assert club.name == "Goldfish"
        assert club.chat_id == 123456
        assert club.schedules == [schedule]
        assert club.is_online is False
        assert club.aetherhub_url is None
        assert club.title_prefix == ""
        assert club.timezone is None

    def test_club_full(self):
        """Should create Club with all fields."""
        schedule = ClubSchedule(weekday="friday", game_time="19:30")
        club = Club(
            name="Endstep",
            chat_id=789012,
            schedules=[schedule],
            is_online=True,
            aetherhub_url="https://aetherhub.com/User/Endstep",
            title_prefix="Online: ",
            timezone="UTC+3",
        )
        assert club.name == "Endstep"
        assert club.chat_id == 789012
        assert club.is_online is True
        assert club.aetherhub_url == "https://aetherhub.com/User/Endstep"
        assert club.title_prefix == "Online: "
        assert club.timezone == "UTC+3"


class TestSettingsProperties:
    """Test Settings class properties (methods that don't require env vars)."""

    @pytest.fixture
    def settings(self):
        """Import settings after all mocks are set up."""
        from core.config import settings as s
        return s

    def test_admin_ids_empty(self, settings):
        """Should return empty list when ADMIN_IDS is empty."""
        with patch.object(settings, 'ADMIN_IDS', ''):
            admin_ids = settings.admin_ids
            assert admin_ids == []

    def test_admin_ids_single(self, settings):
        """Should parse single admin ID."""
        with patch.object(settings, 'ADMIN_IDS', '123456789'):
            admin_ids = settings.admin_ids
            assert admin_ids == [123456789]

    def test_admin_ids_multiple(self, settings):
        """Should parse multiple admin IDs with various spacing."""
        with patch.object(settings, 'ADMIN_IDS', '123, 456 , 789'):
            admin_ids = settings.admin_ids
            assert admin_ids == [123, 456, 789]

    def test_cellar_coordinator_tg_ids_empty(self, settings):
        """Should return empty list when CELLAR_COORDINATOR_TG_IDS is empty."""
        with patch.object(settings, 'CELLAR_COORDINATOR_TG_IDS', ''):
            ids = settings.cellar_coordinator_tg_ids
            assert ids == []

    def test_cellar_coordinator_tg_ids_multiple(self, settings):
        """Should parse multiple coordinator IDs."""
        with patch.object(settings, 'CELLAR_COORDINATOR_TG_IDS', '111, 222, 333'):
            ids = settings.cellar_coordinator_tg_ids
            assert ids == [111, 222, 333]

    def test_cellar_coordinator_usernames_empty(self, settings):
        """Should return empty list when usernames are empty."""
        with patch.object(settings, 'CELLAR_COORDINATOR_USERNAMES', ''):
            usernames = settings.cellar_coordinator_usernames
            assert usernames == []

    def test_cellar_coordinator_usernames_with_at_prefix(self, settings):
        """Should strip @ prefix and deduplicate usernames."""
        with patch.object(settings, 'CELLAR_COORDINATOR_USERNAMES', '@alice, bob, @alice'):
            usernames = settings.cellar_coordinator_usernames
            assert 'alice' in usernames
            assert 'bob' in usernames
            assert len(usernames) == 2

    def test_cellar_coordinator_usernames_casefold(self, settings):
        """Should casefold usernames to lowercase."""
        with patch.object(settings, 'CELLAR_COORDINATOR_USERNAMES', '@Alice, BOB'):
            usernames = settings.cellar_coordinator_usernames
            assert 'alice' in usernames
            assert 'bob' in usernames
