"""Unit tests for core.database module."""
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import database_connect_args, get_db


class TestDatabaseConnectArgs:
    """Test database_connect_args() function."""

    def test_empty_schema(self):
        """Should return empty dict when DATABASE_SCHEMA is empty."""
        with patch('core.database.settings') as mock_settings:
            mock_settings.DATABASE_SCHEMA = ""
            result = database_connect_args()
            assert result == {}

    def test_valid_schema(self):
        """Should return options dict for valid PostgreSQL schema."""
        with patch('core.database.settings') as mock_settings:
            mock_settings.DATABASE_SCHEMA = "test_schema"
            mock_url = MagicMock()
            mock_url.scheme = "postgresql"
            mock_settings.DATABASE_URL = mock_url
            result = database_connect_args()
            assert result == {"options": "-csearch_path=test_schema"}

    def test_valid_schema_with_numbers_and_underscores(self):
        """Should accept schema names with numbers and underscores."""
        with patch('core.database.settings') as mock_settings:
            mock_settings.DATABASE_SCHEMA = "schema_v1_test"
            mock_url = MagicMock()
            mock_url.scheme = "postgresql"
            mock_settings.DATABASE_URL = mock_url
            result = database_connect_args()
            assert result == {"options": "-csearch_path=schema_v1_test"}

    def test_invalid_schema_starts_with_number(self):
        """Should reject schema starting with number."""
        with patch('core.database.settings') as mock_settings:
            mock_settings.DATABASE_SCHEMA = "1schema"
            mock_url = MagicMock()
            mock_url.scheme = "postgresql"
            mock_settings.DATABASE_URL = mock_url
            with pytest.raises(ValueError, match="DATABASE_SCHEMA must be a lowercase PostgreSQL identifier"):
                database_connect_args()

    def test_invalid_schema_uppercase(self):
        """Should reject schema with uppercase letters."""
        with patch('core.database.settings') as mock_settings:
            mock_settings.DATABASE_SCHEMA = "TestSchema"
            mock_url = MagicMock()
            mock_url.scheme = "postgresql"
            mock_settings.DATABASE_URL = mock_url
            with pytest.raises(ValueError, match="DATABASE_SCHEMA must be a lowercase PostgreSQL identifier"):
                database_connect_args()

    def test_invalid_schema_special_chars(self):
        """Should reject schema with special characters."""
        with patch('core.database.settings') as mock_settings:
            mock_settings.DATABASE_SCHEMA = "schema-test"
            mock_url = MagicMock()
            mock_url.scheme = "postgresql"
            mock_settings.DATABASE_URL = mock_url
            with pytest.raises(ValueError, match="DATABASE_SCHEMA must be a lowercase PostgreSQL identifier"):
                database_connect_args()

    def test_schema_with_non_postgresql(self):
        """Should raise error if using schema with non-PostgreSQL database."""
        with patch('core.database.settings') as mock_settings:
            mock_settings.DATABASE_SCHEMA = "test_schema"
            mock_url = MagicMock()
            mock_url.scheme = "sqlite"
            mock_settings.DATABASE_URL = mock_url
            with pytest.raises(ValueError, match="DATABASE_SCHEMA is supported only for PostgreSQL"):
                database_connect_args()


class TestGetDb:
    """Test get_db() generator function."""

    def test_get_db_yields_session(self):
        """Should yield a database session."""
        # Mock SessionLocal
        mock_session = MagicMock()
        with patch('core.database.SessionLocal', return_value=mock_session):
            generator = get_db()
            db = next(generator)
            assert db == mock_session

    def test_get_db_closes_session_on_success(self):
        """Should close session after successful yield."""
        mock_session = MagicMock()
        with patch('core.database.SessionLocal', return_value=mock_session):
            generator = get_db()
            db = next(generator)
            try:
                generator.send(None)
            except StopIteration:
                pass
            mock_session.close.assert_called_once()

    def test_get_db_closes_session_on_exception(self):
        """Should close session even if exception occurs during yield."""
        mock_session = MagicMock()
        with patch('core.database.SessionLocal', return_value=mock_session):
            generator = get_db()
            db = next(generator)
            try:
                generator.throw(ValueError("test error"))
            except ValueError:
                pass
            mock_session.close.assert_called_once()
