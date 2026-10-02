import pytest
import os
import sys

# Add src to path for testing
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

def test_database_initialization():
    """Test that the database module can be imported properly."""
    try:
        import database
        assert database is not None
    except ImportError:
        pytest.fail("Failed to import database")

def test_environment_vars():
    """Test if basic env defaults are accessible."""
    db_path = os.getenv('DB_PATH', 'data/cropguard.db')
    assert 'cropguard.db' in db_path
