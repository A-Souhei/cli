#!/usr/bin/env python
"""Test script for the session feature."""

from src.session import SessionManager


def test_session_manager():
    """Test SessionManager functionality."""
    print("Testing SessionManager...")

    sm = SessionManager()

    # Test 1: No active session initially
    assert not sm.is_active(), "❌ Session should not be active initially"
    print("✓ Test 1: No active session initially")

    # Test 2: Start a session
    session_id = sm.start_session(metadata={"test": True})
    assert sm.is_active(), "❌ Session should be active after start"
    assert session_id is not None, "❌ Session ID should not be None"
    print(f"✓ Test 2: Session started with ID: {session_id[:8]}...")

    # Test 3: Get session info
    info = sm.get_session_info()
    assert info["session_id"] == session_id, "❌ Session ID mismatch"
    assert info["active"] is True, "❌ Session should be active"
    assert info["num_interactions"] == 0, "❌ Should have 0 interactions initially"
    print("✓ Test 3: Session info retrieved correctly")

    # Test 4: Add interactions
    sm.add_interaction("What is 2+2?", "4", metadata={"test": True})
    sm.add_interaction("What is the capital of France?", "Paris", metadata={"test": True})
    sm.add_interaction("Who wrote Romeo and Juliet?", "William Shakespeare", metadata={"test": True})

    assert len(sm.get_session_history()) == 3, "❌ Should have 3 interactions"
    print("✓ Test 4: Added 3 interactions")

    # Test 5: Get session context
    context = sm.get_session_context(max_interactions=2)
    assert "What is the capital of France?" in context, "❌ Recent interaction should be in context"
    assert "Who wrote Romeo and Juliet?" in context, "❌ Most recent interaction should be in context"
    print("✓ Test 5: Session context retrieved (limited to 2 interactions)")

    # Test 6: Get full context
    full_context = sm.get_session_context()
    assert "What is 2+2?" in full_context, "❌ First interaction should be in full context"
    assert "3 previous interactions" in full_context, "❌ Should show 3 interactions in header"
    print("✓ Test 6: Full session context retrieved")

    # Test 7: End session
    summary = sm.end_session()
    assert summary is not None, "❌ Summary should not be None"
    assert summary["num_interactions"] == 3, "❌ Should report 3 interactions"
    assert not sm.is_active(), "❌ Session should not be active after end"
    print("✓ Test 7: Session ended successfully")

    # Test 8: Session info after end
    info_after = sm.get_session_info()
    assert info_after == {}, "❌ Info should be empty after session end"
    print("✓ Test 8: No session info after end")

    # Test 9: End session when none active
    summary2 = sm.end_session()
    assert summary2 is None, "❌ Should return None when no active session"
    print("✓ Test 9: Handled ending non-existent session gracefully")

    # Test 10: New session after ending
    session_id2 = sm.start_session()
    assert sm.is_active(), "❌ Should be able to start new session"
    assert session_id2 != session_id, "❌ New session should have different ID"
    assert len(sm.get_session_history()) == 0, "❌ New session should have empty history"
    sm.end_session()
    print("✓ Test 10: New session after ending previous one")

    print("\n✅ All tests passed!")


def test_session_title():
    """Test SessionManager title functionality."""
    print("\nTesting Session Title functionality...")

    sm = SessionManager()

    # Test 11: Title is None initially
    session_id = sm.start_session()
    assert sm.get_title() is None, "❌ Title should be None initially"
    print("✓ Test 11: Title is None initially")

    # Test 12: Manual title setting
    sm.set_title("Test Session Title")
    assert sm.get_title() == "Test Session Title", "❌ Title should be set"
    print("✓ Test 12: Manual title setting works")

    # Test 13: Title in session info
    info = sm.get_session_info()
    assert info["title"] == "Test Session Title", "❌ Title should be in session info"
    print("✓ Test 13: Title included in session info")

    # Test 14: Title in end session summary
    summary = sm.end_session()
    assert summary["title"] == "Test Session Title", "❌ Title should be in summary"
    print("✓ Test 14: Title included in end session summary")

    # Test 15: Title reset on new session
    sm.start_session()
    assert sm.get_title() is None, "❌ Title should be None for new session"
    sm.end_session()
    print("✓ Test 15: Title reset on new session")

    print("\n✅ All title tests passed!")


if __name__ == "__main__":
    test_session_manager()
    test_session_title()
