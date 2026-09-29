"""Unit tests for bot/handlers/create_tournament.py handler."""

import pytest
from datetime import date, datetime, time, timedelta, timezone
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

from bot.handlers.base import HandlerResult
from bot.handlers.create_tournament import CreateTournamentWizardHandler, ANNOUNCE_DAYS, EVENT_DAYS
from core.clubs import ClubIdentity
from services.tournament_creation import InvalidCreationPlan


@pytest.fixture
def mock_plans():
    """Mock TournamentCreationPlanService."""
    plans = Mock()
    plans.create_plan = Mock()
    return plans


@pytest.fixture
def mock_users():
    """Mock UserService."""
    users = Mock()
    users.is_admin = Mock(return_value=True)
    return users


@pytest.fixture
def mock_keyboards():
    """Mock Keyboards."""
    kb = Mock()
    kb.create_tournament_club_keyboard = Mock(return_value=Mock())
    kb.create_tournament_announce_date_keyboard = Mock(return_value=Mock())
    kb.create_tournament_time_keyboard = Mock(return_value=Mock())
    kb.create_tournament_date_keyboard = Mock(return_value=Mock())
    kb.create_tournament_confirm_keyboard = Mock(return_value=Mock())
    return kb


@pytest.fixture
def mock_club_settings():
    """Mock ClubAnnouncementSettingsService."""
    settings = Mock()
    settings.current_target = Mock(return_value=Mock(label="Основной чат"))
    return settings


@pytest.fixture
def handler(mock_plans, mock_users, mock_keyboards, mock_club_settings):
    """Create CreateTournamentWizardHandler."""
    return CreateTournamentWizardHandler(
        plans=mock_plans,
        users=mock_users,
        keyboards=mock_keyboards,
        club_settings=mock_club_settings,
    )


@pytest.fixture
def mock_club_identity():
    """Create mock ClubIdentity."""
    identity = Mock(spec=ClubIdentity)
    identity.name = "Лавка"
    identity.title_prefix = "⌚ "
    identity.is_online = False
    identity.timezone = "Europe/Moscow"
    return identity


@pytest.fixture
def today_moscow():
    """Get today's date in Moscow timezone."""
    tz = ZoneInfo("Europe/Moscow")
    return datetime.now(tz).date()


class TestHandleStart:
    """Tests for handle_start method."""

    def test_handle_start_not_admin(self, handler, mock_users):
        """Test when user is not admin."""
        mock_users.is_admin.return_value = False
        result = handler.handle_start(123)
        assert "админ" in result.text.lower()

    def test_handle_start_admin(self, handler, mock_users):
        """Test successful start as admin."""
        with patch('bot.handlers.create_tournament.club_identities') as mock_identities:
            identity1 = Mock(title_prefix="🏆 ", name="Лавка")
            identity2 = Mock(title_prefix="🎮 ", name="Online Club")
            mock_identities.return_value = [identity1, identity2]

            result = handler.handle_start(123)
            assert "Создание турнира" in result.text
            assert result.keyboard is not None


class TestHandleClub:
    """Tests for handle_club method."""

    def test_handle_club_not_admin(self, handler, mock_users):
        """Test when user is not admin."""
        mock_users.is_admin.return_value = False
        result = handler.handle_club(123, {}, 0)
        assert result.is_alert is True

    def test_handle_club_invalid_index(self, handler):
        """Test with invalid club index."""
        with patch('bot.handlers.create_tournament.club_identities') as mock_identities:
            mock_identities.return_value = [Mock()]
            result = handler.handle_club(123, {}, 999)
            assert result.is_alert is True
            assert "не найден" in result.text.lower()

    def test_handle_club_valid(self, handler, mock_club_identity):
        """Test successful club selection."""
        draft = {}
        with patch('bot.handlers.create_tournament.club_identities') as mock_identities:
            mock_identities.return_value = [mock_club_identity]

            with patch.object(handler, '_announce_date_result') as mock_announce:
                mock_announce.return_value = HandlerResult("announce date")
                result = handler.handle_club(123, draft, 0)

            assert draft["club_name"] == "Лавка"
            assert draft["step"] == "announce_date"
            assert result is not None


class TestHandleAnnounceNow:
    """Tests for handle_announce_now method."""

    def test_announce_now_not_admin(self, handler, mock_users):
        """Test when user is not admin."""
        mock_users.is_admin.return_value = False
        result = handler.handle_announce_now(123, {})
        assert result.is_alert is True

    def test_announce_now_invalid_step(self, handler):
        """Test with invalid step."""
        result = handler.handle_announce_now(123, {"step": "wrong"})
        assert result.is_alert is True

    def test_announce_now_success(self, handler, mock_club_identity):
        """Test successful announce now."""
        draft = {"club_name": "Лавка", "step": "announce_date"}

        with patch('bot.handlers.create_tournament.club_identities') as mock_identities:
            mock_identities.return_value = [mock_club_identity]

            with patch.object(handler, '_event_date_result') as mock_event:
                mock_event.return_value = HandlerResult("event date")
                result = handler.handle_announce_now(123, draft)

            assert draft["announce_now"] is True
            assert draft["step"] == "event_date"
            assert "announce_date" not in draft


class TestHandleAnnounceDate:
    """Tests for handle_announce_date method."""

    def test_announce_date_not_admin(self, handler, mock_users):
        """Test when user is not admin."""
        mock_users.is_admin.return_value = False
        result = handler.handle_announce_date(123, {}, "20240101")
        assert result.is_alert is True

    def test_announce_date_invalid_step(self, handler):
        """Test with invalid step."""
        result = handler.handle_announce_date(123, {"step": "wrong"}, "20240101")
        assert result.is_alert is True

    def test_announce_date_invalid_format(self, handler, mock_club_identity):
        """Test with invalid date format."""
        draft = {"club_name": "Лавка", "step": "announce_date"}

        with patch('bot.handlers.create_tournament.club_identities') as mock_identities:
            mock_identities.return_value = [mock_club_identity]
            result = handler.handle_announce_date(123, draft, "invalid")

            assert result.is_alert is True

    def test_announce_date_out_of_range(self, handler, mock_club_identity):
        """Test with date out of allowed range."""
        draft = {"club_name": "Лавка", "step": "announce_date"}
        far_future = datetime.now(ZoneInfo("Europe/Moscow")) + timedelta(days=30)

        with patch('bot.handlers.create_tournament.club_identities') as mock_identities:
            mock_identities.return_value = [mock_club_identity]
            result = handler.handle_announce_date(123, draft, far_future.strftime("%Y%m%d"))

            assert result.is_alert is True


class TestHandleAnnounceTime:
    """Tests for handle_announce_time method."""

    def test_announce_time_invalid_time(self, handler, mock_club_identity):
        """Test with invalid time."""
        draft = {"club_name": "Лавка", "step": "announce_time"}

        with patch('bot.handlers.create_tournament.club_identities') as mock_identities:
            mock_identities.return_value = [mock_club_identity]
            result = handler.handle_announce_time(123, draft, "2599")

            assert result.is_alert is True
            assert "время" in result.text.lower()

    def test_announce_time_success(self, handler, mock_club_identity):
        """Test successful time selection."""
        draft = {"club_name": "Лавка", "step": "announce_time"}

        with patch('bot.handlers.create_tournament.club_identities') as mock_identities:
            mock_identities.return_value = [mock_club_identity]

            with patch.object(handler, '_event_date_result') as mock_event:
                mock_event.return_value = HandlerResult("event date")
                result = handler.handle_announce_time(123, draft, "0830")

            assert draft["announce_time"] == "08:30"
            assert draft["step"] == "event_date"


class TestHandleEventDate:
    """Tests for handle_event_date method."""

    def test_event_date_before_announce_date(self, handler, mock_club_identity):
        """Test when event date is before announce date."""
        today = datetime.now(ZoneInfo("Europe/Moscow")).date()
        tomorrow = today + timedelta(days=1)
        day_after = today + timedelta(days=2)

        draft = {
            "club_name": "Лавка",
            "step": "event_date",
            "announce_date": tomorrow.isoformat(),
            "announce_time": "10:00"
        }

        with patch('bot.handlers.create_tournament.club_identities') as mock_identities:
            mock_identities.return_value = [mock_club_identity]
            # Pass today's date (which is before announce_date)
            result = handler.handle_event_date(123, draft, today.strftime("%Y%m%d"))

            assert result.is_alert is True
            assert "раньше" in result.text.lower()

    def test_event_date_success(self, handler, mock_club_identity):
        """Test successful event date selection."""
        today = datetime.now(ZoneInfo("Europe/Moscow")).date()
        future_date = today + timedelta(days=5)

        draft = {
            "club_name": "Лавка",
            "step": "event_date",
            "announce_now": True
        }

        with patch('bot.handlers.create_tournament.club_identities') as mock_identities:
            mock_identities.return_value = [mock_club_identity]

            with patch.object(handler, '_event_time_result') as mock_time:
                mock_time.return_value = HandlerResult("event time")
                result = handler.handle_event_date(123, draft, future_date.strftime("%Y%m%d"))

            assert draft["event_date"] == future_date.isoformat()
            assert draft["step"] == "event_time"


class TestHandleEventTime:
    """Tests for handle_event_time method."""

    def test_event_time_invalid_time(self, handler, mock_club_identity):
        """Test with invalid time."""
        draft = {"club_name": "Лавка", "step": "event_time"}

        with patch('bot.handlers.create_tournament.club_identities') as mock_identities:
            mock_identities.return_value = [mock_club_identity]
            result = handler.handle_event_time(123, draft, "9999")

            assert result.is_alert is True

    def test_event_time_success(self, handler, mock_club_identity):
        """Test successful event time selection."""
        today = datetime.now(ZoneInfo("Europe/Moscow")).date()
        future_date = today + timedelta(days=5)

        draft = {
            "club_name": "Лавка",
            "step": "event_time",
            "announce_now": True,
            "event_date": future_date.isoformat()
        }

        with patch('bot.handlers.create_tournament.club_identities') as mock_identities:
            mock_identities.return_value = [mock_club_identity]

            with patch.object(handler, '_validate_datetimes') as mock_validate:
                mock_validate.return_value = None

                with patch.object(handler, '_confirmation_result') as mock_confirm:
                    mock_confirm.return_value = HandlerResult("confirm")
                    result = handler.handle_event_time(123, draft, "1900")

            assert draft["event_time"] == "19:00"
            assert draft["step"] == "confirm"


class TestHandleBack:
    """Tests for handle_back method."""

    def test_handle_back_to_club(self, handler):
        """Test back to club selection."""
        draft = {"club_name": "Лавка", "step": "announce_date"}

        with patch.object(handler, 'handle_start') as mock_start:
            mock_start.return_value = HandlerResult("start")
            result = handler.handle_back(123, draft, "club")

        assert len(draft) == 0  # draft cleared
        mock_start.assert_called_once_with(123)

    def test_handle_back_announce_date(self, handler, mock_club_identity):
        """Test back to announce date."""
        draft = {"club_name": "Лавка", "step": "announce_time"}

        with patch('bot.handlers.create_tournament.club_identities') as mock_identities:
            mock_identities.return_value = [mock_club_identity]

            with patch.object(handler, '_announce_date_result') as mock_announce:
                mock_announce.return_value = HandlerResult("announce date")
                result = handler.handle_back(123, draft, "ad")

            assert draft["step"] == "announce_date"

    def test_handle_back_expired_wizard(self, handler, mock_club_identity):
        """Test back with expired wizard state."""
        draft = {"club_name": "Lav ka", "step": "invalid"}

        with patch('bot.handlers.create_tournament.club_identities') as mock_identities:
            mock_identities.return_value = [mock_club_identity]
            result = handler.handle_back(123, draft, "ad")

            assert result.is_alert is True


class TestHandleConfirm:
    """Tests for handle_confirm method."""

    def test_confirm_not_admin(self, handler, mock_users):
        """Test when user is not admin."""
        mock_users.is_admin.return_value = False
        result = handler.handle_confirm(123, {})
        assert result.is_alert is True

    def test_confirm_validation_error(self, handler, mock_club_identity):
        """Test confirmation with validation error."""
        draft = {"club_name": "Лавка", "step": "confirm"}

        with patch('bot.handlers.create_tournament.club_identities') as mock_identities:
            mock_identities.return_value = [mock_club_identity]

            with patch.object(handler, '_validate_datetimes') as mock_validate:
                mock_validate.return_value = "Validation failed"
                result = handler.handle_confirm(123, draft)

            assert result.is_alert is True

    def test_confirm_creation_plan_error(self, handler, mock_plans, mock_club_identity):
        """Test confirmation with creation plan error."""
        draft = {
            "club_name": "Лавка",
            "step": "confirm",
            "announce_now": True,
            "announce_time": "10:00",
            "event_date": (datetime.now(ZoneInfo("Europe/Moscow")).date() + timedelta(days=5)).isoformat(),
            "event_time": "19:00"
        }

        mock_plans.create_plan.side_effect = InvalidCreationPlan("Plan error")

        with patch('bot.handlers.create_tournament.club_identities') as mock_identities:
            mock_identities.return_value = [mock_club_identity]

            with patch.object(handler, '_validate_datetimes') as mock_validate:
                mock_validate.return_value = None

                result = handler.handle_confirm(123, draft)

            assert result.is_alert is True

    def test_confirm_success(self, handler, mock_plans, mock_club_identity):
        """Test successful confirmation."""
        today = datetime.now(ZoneInfo("Europe/Moscow")).date()
        future_date = today + timedelta(days=5)

        draft = {
            "club_name": "Лавка",
            "step": "confirm",
            "announce_now": True,
            "announce_time": "10:00",
            "event_date": future_date.isoformat(),
            "event_time": "19:00"
        }

        plan = Mock()
        plan.id = 123
        mock_plans.create_plan.return_value = plan

        with patch('bot.handlers.create_tournament.club_identities') as mock_identities:
            mock_identities.return_value = [mock_club_identity]

            with patch.object(handler, '_validate_datetimes') as mock_validate:
                mock_validate.return_value = None

                result = handler.handle_confirm(123, draft)

            assert "✅" in result.text
            assert result.creation_plan_id == 123
            assert len(draft) == 0  # draft cleared


class TestStaticMethods:
    """Tests for static helper methods."""

    def test_parse_time_valid(self):
        """Test _parse_time with valid time."""
        result = CreateTournamentWizardHandler._parse_time("1830")
        assert result == "18:30"

    def test_parse_time_invalid_length(self):
        """Test _parse_time with invalid length."""
        result = CreateTournamentWizardHandler._parse_time("183")
        assert result == ""

    def test_parse_time_non_ascii(self):
        """Test _parse_time with non-ascii characters."""
        result = CreateTournamentWizardHandler._parse_time("18çº")
        assert result == ""

    def test_parse_time_non_digit(self):
        """Test _parse_time with non-digit characters."""
        result = CreateTournamentWizardHandler._parse_time("18ab")
        assert result == ""

    def test_date_label(self):
        """Test _date_label formatting."""
        test_date = date(2024, 1, 8)  # понедельник
        result = CreateTournamentWizardHandler._date_label(test_date)
        assert "08.01.2024" in result
        assert "пн" in result

    def test_creation_icon_online(self):
        """Test _creation_icon for online club."""
        identity = Mock(spec=ClubIdentity)
        identity.is_online = True
        result = CreateTournamentWizardHandler._creation_icon(identity)
        assert result == "🎮"

    def test_creation_icon_offline(self):
        """Test _creation_icon for offline club."""
        identity = Mock(spec=ClubIdentity)
        identity.is_online = False
        result = CreateTournamentWizardHandler._creation_icon(identity)
        assert result == "🏆"

    def test_now_utc_naive_default(self):
        """Test _now_utc_naive with default (None)."""
        result = CreateTournamentWizardHandler._now_utc_naive(None)
        assert isinstance(result, datetime)
        # Should be close to current UTC time
        assert abs((datetime.now(timezone.utc).replace(tzinfo=None) - result).total_seconds()) < 5

    def test_now_utc_naive_custom(self):
        """Test _now_utc_naive with custom time."""
        custom_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = CreateTournamentWizardHandler._now_utc_naive(custom_time)
        assert result == datetime(2024, 1, 1, 12, 0, 0)

    def test_now_local_default(self, handler):
        """Test _now_local with default (None)."""
        identity = Mock(timezone="Europe/Moscow")
        result = handler._now_local(identity, None)
        assert isinstance(result, datetime)

    def test_now_local_custom(self, handler):
        """Test _now_local with custom time."""
        identity = Mock(timezone="Europe/Moscow")
        custom_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = handler._now_local(identity, custom_time)
        assert isinstance(result, datetime)


class TestPrivateHelpers:
    """Tests for private helper methods."""

    def test_authorized_identity_not_admin(self, handler, mock_users):
        """Test _authorized_identity when not admin."""
        mock_users.is_admin.return_value = False
        result = handler._authorized_identity(123, {})
        assert isinstance(result, HandlerResult)
        assert result.is_alert is True

    def test_authorized_identity_wrong_step(self, handler):
        """Test _authorized_identity with wrong step."""
        result = handler._authorized_identity(123, {"step": "wrong"}, expected_step="expected")
        assert isinstance(result, HandlerResult)
        assert result.is_alert is True

    def test_authorized_identity_club_not_found(self, handler):
        """Test _authorized_identity when club not found."""
        draft = {"club_name": "NonExistent", "step": "announce_date"}

        with patch('bot.handlers.create_tournament.club_identities') as mock_identities:
            mock_identities.return_value = [Mock(name="OtherClub")]
            result = handler._authorized_identity(123, draft, expected_step="announce_date")

            assert isinstance(result, HandlerResult)
            assert result.is_alert is True

    def test_authorized_identity_success(self, handler, mock_club_identity):
        """Test successful _authorized_identity."""
        draft = {"club_name": "Лавка", "step": "announce_date"}

        with patch('bot.handlers.create_tournament.club_identities') as mock_identities:
            mock_identities.return_value = [mock_club_identity]
            result = handler._authorized_identity(123, draft, expected_step="announce_date")

            assert isinstance(result, ClubIdentity)

    def test_date_options(self, handler, mock_club_identity):
        """Test _date_options generates correct dates."""
        now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = handler._date_options(mock_club_identity, now, 8)

        assert len(result) == 8
        # All results should be tuples of (date_str, label)
        for date_str, label in result:
            assert len(date_str) == 8  # YYYYMMDD format
            assert "." in label  # Date label format

    def test_parse_allowed_date_valid(self, handler, mock_club_identity):
        """Test _parse_allowed_date with valid date."""
        now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=ZoneInfo("Europe/Moscow"))
        # Use a date that's within the allowed range from the 'now' parameter
        tomorrow_str = (now.date() + timedelta(days=1)).strftime("%Y%m%d")

        result = handler._parse_allowed_date(tomorrow_str, mock_club_identity, now, 8)
        assert result is not None

    def test_parse_allowed_date_invalid_format(self, handler, mock_club_identity):
        """Test _parse_allowed_date with invalid format."""
        result = handler._parse_allowed_date("invalid", mock_club_identity, None, 8)
        assert result is None

    def test_utc_datetimes_announce_now(self, handler, mock_club_identity):
        """Test _utc_datetimes with announce_now."""
        today = datetime.now(ZoneInfo("Europe/Moscow")).date()
        draft = {
            "announce_now": True,
            "event_date": (today + timedelta(days=5)).isoformat(),
            "event_time": "19:00"
        }

        announce_at, event_at = handler._utc_datetimes(mock_club_identity, draft, None)
        assert isinstance(announce_at, datetime)
        assert isinstance(event_at, datetime)
        assert event_at > announce_at

    def test_validate_datetimes_past_announce_time(self, handler, mock_club_identity):
        """Test _validate_datetimes with past announce time."""
        past = datetime.now(timezone.utc) - timedelta(hours=2)
        draft = {
            "announce_now": False,
            "announce_date": (past.date() - timedelta(days=1)).isoformat(),
            "announce_time": "10:00",
            "event_date": (past.date() + timedelta(days=2)).isoformat(),
            "event_time": "19:00"
        }

        error = handler._validate_datetimes(mock_club_identity, draft, past)
        assert error is not None
        assert "публикации" in error.lower()

    def test_validate_datetimes_past_event_time(self, handler, mock_club_identity):
        """Test _validate_datetimes with past event time."""
        past = datetime.now(timezone.utc) - timedelta(hours=2)
        draft = {
            "announce_now": True,
            "event_date": past.date().isoformat(),
            "event_time": "10:00"
        }

        error = handler._validate_datetimes(mock_club_identity, draft, past)
        assert error is not None
        assert "прошло" in error.lower()

    def test_validate_datetimes_event_before_announce(self, handler, mock_club_identity):
        """Test _validate_datetimes when event is before announce."""
        now = datetime.now(timezone.utc) + timedelta(hours=1)
        future_announce = now + timedelta(days=5)
        future_event = future_announce - timedelta(days=1)

        draft = {
            "announce_now": False,
            "announce_date": future_announce.date().isoformat(),
            "announce_time": "10:00",
            "event_date": future_event.date().isoformat(),
            "event_time": "19:00"
        }

        error = handler._validate_datetimes(mock_club_identity, draft, now)
        assert error is not None
