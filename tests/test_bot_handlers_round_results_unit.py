"""Unit tests for bot/handlers/round_results.py handler."""

import pytest
from unittest.mock import MagicMock, Mock, patch

from bot.handlers.base import HandlerResult
from bot.handlers.round_results import DeliveryResult, RoundResultsHandler
from core import models
from services.round_results import RoundResultError


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = Mock()
    return db


@pytest.fixture
def mock_keyboards():
    """Mock keyboards helper."""
    kb = Mock()
    kb.round_status_keyboard = Mock(return_value=Mock())
    kb.round_score_values_keyboard = Mock(return_value=Mock())
    kb.round_result_response_keyboard = Mock(return_value=Mock())
    kb.round_result_preview_keyboard = Mock(return_value=Mock())
    kb.round_admin_matches_keyboard = Mock(return_value=Mock())
    kb.round_summary_keyboard = Mock(return_value=Mock())
    return kb


@pytest.fixture
def handler(mock_db, mock_keyboards):
    """Create RoundResultsHandler with mocked dependencies."""
    handler = RoundResultsHandler(mock_db, keyboards=mock_keyboards)
    handler.results = Mock()
    handler.users = Mock()
    return handler


class TestDeliveryResult:
    """Tests for DeliveryResult dataclass."""

    def test_delivery_result_screen_only(self):
        """Test DeliveryResult with only screen."""
        screen = HandlerResult("text")
        result = DeliveryResult(screen=screen)
        assert result.screen == screen
        assert result.recipient_tg_id is None
        assert result.recipient_text is None
        assert result.recipient_keyboard is None

    def test_delivery_result_with_all_fields(self):
        """Test DeliveryResult with all fields set."""
        screen = HandlerResult("screen text")
        kb = Mock()
        result = DeliveryResult(
            screen=screen,
            recipient_tg_id=123,
            recipient_text="recip text",
            recipient_keyboard=kb,
        )
        assert result.screen == screen
        assert result.recipient_tg_id == 123
        assert result.recipient_text == "recip text"
        assert result.recipient_keyboard == kb

    def test_delivery_result_frozen(self):
        """Test that DeliveryResult is frozen (immutable)."""
        result = DeliveryResult(screen=HandlerResult("text"))
        with pytest.raises(AttributeError):
            result.recipient_tg_id = 999


class TestHandleRoundStatus:
    """Tests for handle_round_status method."""

    def test_handle_round_status_tournament_not_found(self, handler):
        """Test when tournament doesn't exist."""
        handler.db.get.return_value = None
        result = handler.handle_round_status(999, 123)
        assert isinstance(result, HandlerResult)
        assert "не найден" in result.text.lower()
        assert result.is_alert is True

    def test_handle_round_status_no_pairings(self, handler):
        """Test when no pairings loaded yet."""
        tournament = Mock(spec=models.Tournament)
        handler.db.get.return_value = tournament
        handler.db.execute.return_value.scalars.return_value = []
        result = handler.handle_round_status(1, 123)
        assert "паринги" in result.text.lower()
        assert result.is_alert is True

    def test_handle_round_status_user_can_report(self, handler):
        """Test when user is in latest round and can report."""
        tournament = Mock(spec=models.Tournament)
        tournament.title = "Test Tourney"
        tournament.status = Mock(label_ru="Раунд 3")
        handler.db.get.return_value = tournament

        # Mock round numbers
        handler.db.execute.return_value.scalars.return_value = [1, 2, 3]

        # Mock matches
        match = Mock(spec=models.RoundMatch)
        match.player2_name = "Opponent"
        match.player1_user_id = 101
        match.player2_user_id = 102
        handler.results.list_round.return_value = [match]

        # Mock user is participant in latest round
        user = Mock(spec=models.User)
        user.id = 101
        handler.users.get_by_tg_id.return_value = user
        handler.users.is_admin.return_value = False

        result = handler.handle_round_status(1, 123, round_number=3)
        assert isinstance(result, HandlerResult)
        assert result.parse_mode == "HTML"

    def test_handle_round_status_admin_user(self, handler):
        """Test when admin user views round status."""
        tournament = Mock(spec=models.Tournament)
        tournament.title = "Test"
        tournament.status = Mock(label_ru="Status")
        handler.db.get.return_value = tournament
        handler.db.execute.return_value.scalars.return_value = [1]
        handler.results.list_round.return_value = []

        user = Mock()
        user.id = 1
        handler.users.get_by_tg_id.return_value = user
        handler.users.is_admin.return_value = True

        result = handler.handle_round_status(1, 123)
        assert isinstance(result, HandlerResult)


class TestHandleOpen:
    """Tests for handle_open method."""

    def test_handle_open_user_not_found(self, handler):
        """Test when user doesn't exist."""
        handler.results.current_match_for_user.side_effect = RoundResultError("not found")
        result = handler.handle_open(1, 123)
        assert result.is_alert is True

    def test_handle_open_user_bye_round(self, handler):
        """Test when user has BYE in this round."""
        match = Mock(spec=models.RoundMatch)
        match.round_number = 2
        match.player2_name = None
        handler.results.current_match_for_user.return_value = match
        actor = Mock()
        handler.users.get_by_tg_id.return_value = actor

        result = handler.handle_open(1, 123)
        assert "BYE" in result.text
        assert "не нужно" in result.text

    def test_handle_open_match_already_confirmed(self, handler):
        """Test when match result is already confirmed."""
        match = Mock(spec=models.RoundMatch)
        match.round_number = 1
        match.player2_name = "Opponent"
        match.status = models.RoundMatchStatus.CONFIRMED
        match.player1_wins = 2
        match.player2_wins = 0
        match.player1_name = "Me"
        handler.results.current_match_for_user.return_value = match
        actor = Mock()
        handler.users.get_by_tg_id.return_value = actor

        result = handler.handle_open(1, 123)
        assert "✅" in result.text

    def test_handle_open_pending_proposed_by_actor(self, handler):
        """Test when match is pending and actor proposed it."""
        match = Mock(spec=models.RoundMatch)
        match.round_number = 1
        match.player2_name = "Opponent"
        match.status = models.RoundMatchStatus.PENDING
        match.proposed_by_user_id = 100
        match.player1_wins = 2
        match.player2_wins = 0
        match.player1_name = "Me"
        handler.results.current_match_for_user.return_value = match
        actor = Mock()
        actor.id = 100
        handler.users.get_by_tg_id.return_value = actor

        result = handler.handle_open(1, 123)
        assert "⏳" in result.text
        assert "Ожидаем" in result.text

    def test_handle_open_pending_not_proposed_by_actor(self, handler):
        """Test when match is pending but proposed by opponent."""
        match = Mock(spec=models.RoundMatch)
        match.round_number = 1
        match.player2_name = "Opponent"
        match.status = models.RoundMatchStatus.PENDING
        match.proposed_by_user_id = 200
        match.player1_wins = 2
        match.player2_wins = 0
        match.player1_name = "Me"
        match.id = 1
        match.revision = 1
        handler.results.current_match_for_user.return_value = match
        actor = Mock()
        actor.id = 100
        handler.users.get_by_tg_id.return_value = actor

        result = handler.handle_open(1, 123)
        assert result.keyboard is not None

    def test_handle_open_unreported_state(self, handler):
        """Test when match in UNREPORTED state (no score yet)."""
        match = Mock(spec=models.RoundMatch)
        match.round_number = 1
        match.player2_name = "Opponent"
        match.status = models.RoundMatchStatus.UNREPORTED
        match.player1_user_id = 100
        match.player2_user_id = 200
        match.player1_name = "Me"
        match.player2_name = "You"
        match.id = 1
        handler.results.current_match_for_user.return_value = match
        actor = Mock()
        actor.id = 100
        handler.users.get_by_tg_id.return_value = actor

        result = handler.handle_open(1, 123)
        assert "Сколько игр выиграли вы?" in result.text


class TestHandleOwnWins:
    """Tests for handle_own_wins method."""

    def test_handle_own_wins_success(self, handler):
        """Test successful own wins submission."""
        match = Mock(spec=models.RoundMatch)
        match.id = 1
        match.player1_user_id = 100
        match.player2_user_id = 200
        match.player1_name = "Me"
        match.player2_name = "You"
        actor = Mock()
        actor.id = 100
        handler.results.get_match.return_value = match
        handler.users.get_by_tg_id.return_value = actor
        handler.results.score_from_actor.return_value = None

        result = handler.handle_own_wins(1, 123, own_wins=2)
        assert "Вы выиграли 2" in result.text
        assert "Сколько игр выиграл You?" in result.text

    def test_handle_own_wins_user_not_in_match(self, handler):
        """Test when user is not in the match."""
        match = Mock()
        match.player1_user_id = 100
        match.player2_user_id = 200
        actor = Mock()
        actor.id = 999  # Not in match
        handler.results.get_match.return_value = match
        handler.users.get_by_tg_id.return_value = actor

        with patch.object(handler, '_actor_match') as mock_actor_match:
            mock_actor_match.side_effect = RoundResultError("не принадлежит")
            result = handler.handle_own_wins(1, 123, 2)
            assert result.is_alert is True


class TestHandleOpponentWins:
    """Tests for handle_opponent_wins method."""

    def test_handle_opponent_wins_success(self, handler):
        """Test successful opponent wins submission."""
        match = Mock(spec=models.RoundMatch)
        match.id = 1
        match.player1_user_id = 100
        match.player1_name = "Me"
        match.player2_name = "You"
        actor = Mock()
        actor.id = 100
        handler.results.get_match.return_value = match
        handler.users.get_by_tg_id.return_value = actor
        handler.results.score_from_actor.return_value = (2, 1)

        result = handler.handle_opponent_wins(1, 123, 2, 1)
        assert "Вы указали" in result.text
        assert "Me 2–1 You" in result.text


class TestHandleSend:
    """Tests for handle_send method."""

    def test_handle_send_success_with_opponent(self, handler):
        """Test successful send to opponent with valid tg_id."""
        match = Mock(spec=models.RoundMatch)
        match.id = 1
        match.player1_wins = 2
        match.player2_wins = 0
        match.player1_name = "Me"
        match.player2_name = "You"
        match.revision = 1
        match.player1_user_id = 100
        handler.results.propose.return_value = match

        actor = Mock()
        actor.id = 100
        handler.users.get_by_tg_id.return_value = actor

        opponent = Mock()
        opponent.tg_id = 999
        match.player2_user = opponent

        result = handler.handle_send(1, 123, 2, 0)
        assert isinstance(result, DeliveryResult)
        assert "⏳" in result.screen.text
        assert result.recipient_tg_id == 999

    def test_handle_send_opponent_invalid_tg_id(self, handler):
        """Test send when opponent has invalid tg_id."""
        match = Mock(spec=models.RoundMatch)
        match.id = 1
        match.player1_wins = 2
        match.player2_wins = 0
        match.player1_name = "Me"
        match.player2_name = "You"
        match.revision = 1
        match.player1_user_id = 100
        handler.results.propose.return_value = match

        actor = Mock()
        actor.id = 100
        handler.users.get_by_tg_id.return_value = actor

        opponent = Mock()
        opponent.tg_id = -1  # Invalid (bot user)
        match.player2_user = opponent

        result = handler.handle_send(1, 123, 2, 0)
        assert result.recipient_tg_id is None

    def test_handle_send_error(self, handler):
        """Test send error handling."""
        handler.results.propose.side_effect = RoundResultError("Match not found")
        result = handler.handle_send(999, 123, 2, 0)
        assert isinstance(result, DeliveryResult)
        assert result.screen.is_alert is True


class TestHandleConfirm:
    """Tests for handle_confirm method."""

    def test_handle_confirm_success(self, handler):
        """Test successful confirmation."""
        match = Mock(spec=models.RoundMatch)
        match.id = 1
        match.player1_wins = 2
        match.player2_wins = 0
        match.player1_name = "Me"
        match.player2_name = "You"
        match.proposed_by_user_id = 200
        handler.results.confirm.return_value = match

        proposer = Mock()
        proposer.tg_id = 888
        handler.db.get.return_value = proposer

        result = handler.handle_confirm(1, 1, 100)
        assert isinstance(result, DeliveryResult)
        assert "✅" in result.screen.text
        assert result.recipient_tg_id == 888

    def test_handle_confirm_proposer_not_found(self, handler):
        """Test when proposer user is not found."""
        match = Mock(spec=models.RoundMatch)
        match.id = 1
        match.player1_wins = 2
        match.player2_wins = 0
        match.player1_name = "Me"
        match.player2_name = "You"
        match.proposed_by_user_id = None
        handler.results.confirm.return_value = match
        handler.db.get.return_value = None

        result = handler.handle_confirm(1, 1, 100)
        assert isinstance(result, DeliveryResult)
        assert result.recipient_tg_id is None


class TestHandleReject:
    """Tests for handle_reject method."""

    def test_handle_reject_success(self, handler):
        """Test successful rejection."""
        match = Mock(spec=models.RoundMatch)
        match.id = 1
        match.round_number = 2
        match.player1_user_id = 100
        match.player2_user_id = 200
        match.player1_name = "Me"
        match.player2_name = "You"

        rejected_result = Mock()
        rejected_result.match = match
        rejected_result.proposer_tg_id = 999
        handler.results.reject.return_value = rejected_result

        actor = Mock()
        actor.id = 100
        handler.users.get_by_tg_id.return_value = actor

        result = handler.handle_reject(1, 1, 100)
        assert isinstance(result, DeliveryResult)
        assert "отклонён" in result.screen.text
        assert result.recipient_tg_id == 999

    def test_handle_reject_actor_not_found(self, handler):
        """Test when actor user not found."""
        match = Mock()
        match.id = 1
        rejected_result = Mock()
        rejected_result.match = match
        handler.results.reject.return_value = rejected_result
        handler.users.get_by_tg_id.return_value = None

        result = handler.handle_reject(1, 1, 100)
        assert result.screen.is_alert is True


class TestHandleAdminList:
    """Tests for handle_admin_list method."""

    def test_handle_admin_list_not_admin(self, handler):
        """Test when user is not admin."""
        handler.users.is_admin.return_value = False
        result = handler.handle_admin_list(1, 123)
        assert "прав" in result.text.lower()
        assert result.is_alert is True

    def test_handle_admin_list_no_pairings(self, handler):
        """Test when no pairings loaded."""
        handler.users.is_admin.return_value = True
        handler.results.latest_round_number.return_value = None
        result = handler.handle_admin_list(1, 123)
        assert "паринги" in result.text.lower()

    def test_handle_admin_list_success(self, handler):
        """Test successful admin list."""
        handler.users.is_admin.return_value = True
        handler.results.latest_round_number.return_value = 3
        match1 = Mock()
        match2 = Mock()
        handler.results.list_round.return_value = [match1, match2]

        result = handler.handle_admin_list(1, 123)
        assert "Результаты раунда 3" in result.text


class TestHandleAdminMatch:
    """Tests for handle_admin_match method."""

    def test_handle_admin_match_not_admin(self, handler):
        """Test when user is not admin."""
        handler.users.is_admin.return_value = False
        result = handler.handle_admin_match(1, 123)
        assert result.is_alert is True

    def test_handle_admin_match_success(self, handler):
        """Test successful admin match view."""
        handler.users.is_admin.return_value = True
        match = Mock(spec=models.RoundMatch)
        match.id = 1
        match.player1_name = "Player A"
        match.player2_name = "Player B"
        handler.results.get_match.return_value = match

        result = handler.handle_admin_match(1, 123)
        assert "Player A против Player B" in result.text


class TestHandleAdminP1:
    """Tests for handle_admin_p1 method."""

    def test_handle_admin_p1_not_admin(self, handler):
        """Test when user is not admin."""
        handler.users.is_admin.return_value = False
        result = handler.handle_admin_p1(1, 123, 2)
        assert result.is_alert is True

    def test_handle_admin_p1_success(self, handler):
        """Test successful admin p1 wins submission."""
        handler.users.is_admin.return_value = True
        match = Mock(spec=models.RoundMatch)
        match.id = 1
        match.player1_name = "Player A"
        match.player2_name = "Player B"
        handler.results.get_match.return_value = match

        result = handler.handle_admin_p1(1, 123, 2)
        assert "Player A выиграл 2" in result.text
        assert "Player B" in result.text


class TestHandleAdminP2:
    """Tests for handle_admin_p2 method."""

    def test_handle_admin_p2_success(self, handler):
        """Test successful admin p2 wins submission."""
        match = Mock(spec=models.RoundMatch)
        match.id = 1
        match.tournament_id = 1
        match.player1_wins = 2
        match.player2_wins = 1
        match.player1_name = "A"
        match.player2_name = "B"
        handler.results.admin_set.return_value = match

        # Mock handle_admin_list chain
        handler.users.is_admin.return_value = True
        handler.results.latest_round_number.return_value = 3
        handler.results.list_round.return_value = []

        result = handler.handle_admin_p2(1, 123, 2, 1)
        assert "Сохранено" in result.answer_text


class TestHandleSummary:
    """Tests for handle_summary method."""

    def test_handle_summary_not_admin(self, handler):
        """Test when user is not admin."""
        handler.users.is_admin.return_value = False
        result = handler.handle_summary(1, 123)
        assert result.is_alert is True

    def test_handle_summary_no_pairings(self, handler):
        """Test when no pairings loaded."""
        handler.users.is_admin.return_value = True
        handler.results.latest_round_number.return_value = None
        result = handler.handle_summary(1, 123)
        assert result.is_alert is True

    def test_handle_summary_success(self, handler):
        """Test successful summary."""
        handler.users.is_admin.return_value = True
        handler.results.latest_round_number.return_value = 3
        handler.results.list_round.return_value = []

        result = handler.handle_summary(1, 123)
        assert isinstance(result, HandlerResult)


class TestHandleToggleView:
    """Tests for handle_toggle_view method."""

    def test_handle_toggle_view_enable(self, handler):
        """Test enabling pairings view."""
        handler.results.set_pairings_view.return_value = True
        result = handler.handle_toggle_view(1, 123)
        assert "паринги" in result.text.lower()

    def test_handle_toggle_view_disable(self, handler):
        """Test disabling pairings view."""
        handler.results.set_pairings_view.return_value = False
        result = handler.handle_toggle_view(1, 123)
        assert "список игроков" in result.text.lower()

    def test_handle_toggle_view_error(self, handler):
        """Test toggle view error."""
        handler.results.set_pairings_view.side_effect = RoundResultError("Permission denied")
        result = handler.handle_toggle_view(1, 123)
        assert result.is_alert is True


class TestStaticMethods:
    """Tests for static/private helper methods."""

    def test_score(self):
        """Test _score static method."""
        match = Mock(spec=models.RoundMatch)
        match.player1_name = "Alice"
        match.player2_name = "Bob"
        match.player1_wins = 2
        match.player2_wins = 0
        score = RoundResultsHandler._score(match)
        assert score == "Alice 2–0 Bob"

    def test_score_values(self):
        """Test _score_values static method."""
        match = Mock(spec=models.RoundMatch)
        match.player1_name = "Charlie"
        match.player2_name = "David"
        score = RoundResultsHandler._score_values(match, 1, 2)
        assert score == "Charlie 1–2 David"

    def test_actor_names_player1(self):
        """Test _actor_names when actor is player1."""
        match = Mock(spec=models.RoundMatch)
        match.player1_user_id = 100
        match.player2_user_id = 200
        match.player1_name = "Me"
        match.player2_name = "You"
        own, opponent = RoundResultsHandler._actor_names(match, 100)
        assert own == "Me"
        assert opponent == "You"

    def test_actor_names_player2(self):
        """Test _actor_names when actor is player2."""
        match = Mock(spec=models.RoundMatch)
        match.player1_user_id = 100
        match.player2_user_id = 200
        match.player1_name = "Me"
        match.player2_name = "You"
        own, opponent = RoundResultsHandler._actor_names(match, 200)
        assert own == "You"
        assert opponent == "Me"

    def test_actor_names_not_in_match(self):
        """Test _actor_names when actor is not in match."""
        match = Mock(spec=models.RoundMatch)
        match.player1_user_id = 100
        match.player2_user_id = 200
        with pytest.raises(RoundResultError):
            RoundResultsHandler._actor_names(match, 999)

    def test_other_user_player1_actor(self):
        """Test _other_user when actor is player1."""
        match = Mock(spec=models.RoundMatch)
        match.player1_user_id = 100
        match.player2_user_id = 200
        opponent_user = Mock()
        match.player2_user = opponent_user
        result = RoundResultsHandler._other_user(match, 100)
        assert result == opponent_user

    def test_other_user_player2_actor(self):
        """Test _other_user when actor is player2."""
        match = Mock(spec=models.RoundMatch)
        match.player1_user_id = 100
        match.player2_user_id = 200
        my_user = Mock()
        match.player1_user = my_user
        result = RoundResultsHandler._other_user(match, 200)
        assert result == my_user

    def test_other_user_not_in_match(self):
        """Test _other_user when actor is not in match."""
        match = Mock(spec=models.RoundMatch)
        match.player1_user_id = 100
        match.player2_user_id = 200
        result = RoundResultsHandler._other_user(match, 999)
        assert result is None

    def test_confirmation_text_with_proposer(self, handler):
        """Test _confirmation_text with proposer found."""
        match = Mock(spec=models.RoundMatch)
        match.round_number = 2
        match.player1_wins = 2
        match.player2_wins = 0
        match.player1_name = "P1"
        match.player2_name = "P2"
        match.proposed_by_user_id = 100

        proposer = Mock()
        proposer.last_name = "Smith"
        proposer.first_name = "John"
        proposer.username = "jsmith"
        handler.db.get.return_value = proposer

        text = handler._confirmation_text(match)
        assert "Smith" in text
        assert "раунда 2" in text

    def test_confirmation_text_no_proposer(self, handler):
        """Test _confirmation_text when proposer not found."""
        match = Mock(spec=models.RoundMatch)
        match.round_number = 1
        match.player1_wins = 1
        match.player2_wins = 1
        match.player1_name = "A"
        match.player2_name = "B"
        match.proposed_by_user_id = 999
        handler.db.get.return_value = None

        text = handler._confirmation_text(match)
        assert "Соперник" in text


class TestRoundNumbersQuery:
    """Tests for _round_numbers helper."""

    def test_round_numbers_multiple(self, handler):
        """Test querying multiple round numbers."""
        mock_result = [1, 2, 3]
        handler.db.execute.return_value.scalars.return_value = mock_result
        result = handler._round_numbers(1)
        assert result == [1, 2, 3]

    def test_round_numbers_empty(self, handler):
        """Test querying when no rounds exist."""
        handler.db.execute.return_value.scalars.return_value = []
        result = handler._round_numbers(1)
        assert result == []


class TestActorMatch:
    """Tests for _actor_match helper."""

    def test_actor_match_success(self, handler):
        """Test successful actor match retrieval."""
        match = Mock(spec=models.RoundMatch)
        match.id = 1
        match.player1_user_id = 100
        match.player2_user_id = 200
        handler.results.get_match.return_value = match

        actor = Mock()
        actor.id = 100
        handler.users.get_by_tg_id.return_value = actor

        result_match, result_actor = handler._actor_match(1, 123)
        assert result_match == match
        assert result_actor == actor

    def test_actor_match_user_not_found(self, handler):
        """Test when user not found."""
        handler.users.get_by_tg_id.return_value = None
        with pytest.raises(RoundResultError):
            handler._actor_match(1, 123)

    def test_actor_match_not_in_match(self, handler):
        """Test when actor not in match."""
        match = Mock()
        match.player1_user_id = 100
        match.player2_user_id = 200
        handler.results.get_match.return_value = match

        actor = Mock()
        actor.id = 999  # Not in match
        handler.users.get_by_tg_id.return_value = actor

        with pytest.raises(RoundResultError):
            handler._actor_match(1, 123)
