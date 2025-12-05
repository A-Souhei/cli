"""Unit tests for diff_parser module."""

import pytest
import tempfile
import os
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.diff_parser import (
    DiffHunk,
    parse_unified_diff,
    validate_diff_hunks,
    apply_diff_to_file,
    detect_diff_format,
    InvalidDiffFormatError,
    MissingHunkHeaderError,
    MalformedDiffLineError,
)


class TestDetectDiffFormat:
    """Test diff format detection."""
    
    def test_detect_valid_diff(self):
        """Test detecting a valid unified diff."""
        diff = """--- file.py
+++ file.py
@@ -1,3 +1,3 @@
 line1
-line2
+line2_modified
 line3
"""
        assert detect_diff_format(diff) is True
    
    def test_detect_full_file_content(self):
        """Test detecting full file content (not a diff)."""
        content = """def hello():
    print("hello")
    return 42
"""
        assert detect_diff_format(content) is False
    
    def test_detect_missing_headers(self):
        """Test detecting text missing diff headers."""
        text = """@@ -1,3 +1,3 @@
 line1
-line2
+line2_modified
"""
        assert detect_diff_format(text) is False
    
    def test_detect_missing_hunk(self):
        """Test detecting text with headers but no hunks."""
        text = """--- file.py
+++ file.py
line1
line2
"""
        assert detect_diff_format(text) is False


class TestParseUnifiedDiff:
    """Test unified diff parsing."""
    
    def test_parse_simple_diff(self):
        """Test parsing a simple single-hunk diff."""
        diff = """--- file.py
+++ file.py
@@ -1,3 +1,3 @@
 line1
-line2
+line2_modified
 line3
"""
        hunks = parse_unified_diff(diff)
        
        assert len(hunks) == 1
        hunk = hunks[0]
        assert hunk.old_start == 1
        assert hunk.old_count == 3
        assert hunk.new_start == 1
        assert hunk.new_count == 3
        assert len(hunk.diff_lines) == 4
    
    def test_parse_multiple_hunks(self):
        """Test parsing a diff with multiple hunks."""
        diff = """--- file.py
+++ file.py
@@ -1,3 +1,3 @@
 line1
-line2
+line2_modified
 line3
@@ -10,2 +10,3 @@
 line10
+new_line
 line11
"""
        hunks = parse_unified_diff(diff)
        
        assert len(hunks) == 2
        assert hunks[0].old_start == 1
        assert hunks[1].old_start == 10
    
    def test_parse_without_count(self):
        """Test parsing a hunk header without count (single line change)."""
        diff = """--- file.py
+++ file.py
@@ -1 +1 @@
-old_line
+new_line
"""
        hunks = parse_unified_diff(diff)
        
        assert len(hunks) == 1
        assert hunks[0].old_count == 1
        assert hunks[0].new_count == 1
    
    def test_parse_missing_headers(self):
        """Test parsing fails without --- and +++ headers."""
        diff = """@@ -1,3 +1,3 @@
 line1
-line2
+line2_modified
"""
        with pytest.raises(InvalidDiffFormatError) as exc_info:
            parse_unified_diff(diff)
        assert "must include '---' and '+++' headers" in str(exc_info.value)
    
    def test_parse_malformed_hunk_header(self):
        """Test parsing fails with malformed hunk header."""
        diff = """--- file.py
+++ file.py
@@ invalid header @@
 line1
"""
        with pytest.raises(MissingHunkHeaderError) as exc_info:
            parse_unified_diff(diff)
        assert "Invalid hunk header format" in str(exc_info.value)
    
    def test_parse_invalid_line_prefix(self):
        """Test parsing fails with invalid line prefix."""
        diff = """--- file.py
+++ file.py
@@ -1,2 +1,2 @@
 line1
*invalid_line
"""
        with pytest.raises(MalformedDiffLineError) as exc_info:
            parse_unified_diff(diff)
        assert "Invalid diff line prefix" in str(exc_info.value)
    
    def test_parse_empty_diff(self):
        """Test parsing fails with no hunks."""
        diff = """--- file.py
+++ file.py
"""
        with pytest.raises(InvalidDiffFormatError) as exc_info:
            parse_unified_diff(diff)
        assert "No valid hunks found" in str(exc_info.value)


class TestValidateDiffHunks:
    """Test diff hunk validation."""
    
    def test_validate_simple_diff(self):
        """Test validating a simple correct diff."""
        original = """line1
line2
line3"""
        
        hunks = [
            DiffHunk(
                old_start=1,
                old_count=3,
                new_start=1,
                new_count=3,
                diff_lines=[
                    ' line1',
                    '-line2',
                    '+line2_modified',
                    ' line3'
                ]
            )
        ]
        
        is_valid, error = validate_diff_hunks(original, hunks)
        assert is_valid is True
        assert error == ""
    
    def test_validate_context_mismatch(self):
        """Test validation fails when context doesn't match."""
        original = """line1
line2
line3"""
        
        hunks = [
            DiffHunk(
                old_start=1,
                old_count=3,
                new_start=1,
                new_count=3,
                diff_lines=[
                    ' line1',
                    '-wrong_line',  # Doesn't match line2
                    '+line2_modified',
                    ' line3'
                ]
            )
        ]
        
        is_valid, error = validate_diff_hunks(original, hunks)
        assert is_valid is False
        assert "Deletion mismatch" in error
    
    def test_validate_out_of_bounds(self):
        """Test validation fails when hunk extends beyond file."""
        original = """line1
line2"""
        
        hunks = [
            DiffHunk(
                old_start=1,
                old_count=5,  # File only has 2 lines
                new_start=1,
                new_count=5,
                diff_lines=[' line1', ' line2', ' line3', ' line4', ' line5']
            )
        ]
        
        is_valid, error = validate_diff_hunks(original, hunks)
        assert is_valid is False
        assert "extends beyond file" in error
    
    def test_validate_overlapping_hunks(self):
        """Test validation fails when hunks overlap."""
        original = """line1
line2
line3
line4
line5"""
        
        hunks = [
            DiffHunk(
                old_start=1,
                old_count=3,
                new_start=1,
                new_count=3,
                diff_lines=[' line1', ' line2', ' line3']
            ),
            DiffHunk(
                old_start=2,  # Overlaps with previous hunk
                old_count=2,
                new_start=2,
                new_count=2,
                diff_lines=[' line2', ' line3']
            )
        ]
        
        is_valid, error = validate_diff_hunks(original, hunks)
        assert is_valid is False
        assert "overlap or out of order" in error
    
    def test_validate_multiple_hunks(self):
        """Test validating multiple non-overlapping hunks."""
        original = """line1
line2
line3
line4
line5"""
        
        hunks = [
            DiffHunk(
                old_start=1,
                old_count=2,
                new_start=1,
                new_count=2,
                diff_lines=[' line1', ' line2']
            ),
            DiffHunk(
                old_start=4,
                old_count=2,
                new_start=4,
                new_count=2,
                diff_lines=[' line4', ' line5']
            )
        ]
        
        is_valid, error = validate_diff_hunks(original, hunks)
        assert is_valid is True
        assert error == ""


class TestApplyDiffToFile:
    """Test applying diffs to files."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    def test_apply_simple_modification(self, temp_dir):
        """Test applying a simple modification diff."""
        # Create test file
        file_path = os.path.join(temp_dir, "test.py")
        original_content = """line1
line2
line3"""
        
        with open(file_path, 'w') as f:
            f.write(original_content)
        
        # Create diff hunks
        hunks = [
            DiffHunk(
                old_start=1,
                old_count=3,
                new_start=1,
                new_count=3,
                diff_lines=[
                    ' line1',
                    '-line2',
                    '+line2_modified',
                    ' line3'
                ]
            )
        ]
        
        # Apply diff
        success, message = apply_diff_to_file(file_path, hunks, temp_dir)
        
        assert success is True
        assert "Successfully applied 1 hunk" in message
        
        # Verify file content
        with open(file_path, 'r') as f:
            new_content = f.read()
        
        expected = """line1
line2_modified
line3"""
        assert new_content == expected
    
    def test_apply_addition(self, temp_dir):
        """Test applying a diff that adds lines."""
        file_path = os.path.join(temp_dir, "test.py")
        original_content = """line1
line2"""
        
        with open(file_path, 'w') as f:
            f.write(original_content)
        
        hunks = [
            DiffHunk(
                old_start=1,
                old_count=2,
                new_start=1,
                new_count=4,
                diff_lines=[
                    ' line1',
                    '+new_line1',
                    '+new_line2',
                    ' line2'
                ]
            )
        ]
        
        success, message = apply_diff_to_file(file_path, hunks, temp_dir)
        
        assert success is True
        
        with open(file_path, 'r') as f:
            new_content = f.read()
        
        expected = """line1
new_line1
new_line2
line2"""
        assert new_content == expected
    
    def test_apply_deletion(self, temp_dir):
        """Test applying a diff that deletes lines."""
        file_path = os.path.join(temp_dir, "test.py")
        original_content = """line1
line2
line3
line4"""
        
        with open(file_path, 'w') as f:
            f.write(original_content)
        
        hunks = [
            DiffHunk(
                old_start=1,
                old_count=4,
                new_start=1,
                new_count=2,
                diff_lines=[
                    ' line1',
                    '-line2',
                    '-line3',
                    ' line4'
                ]
            )
        ]
        
        success, message = apply_diff_to_file(file_path, hunks, temp_dir)
        
        assert success is True
        
        with open(file_path, 'r') as f:
            new_content = f.read()
        
        expected = """line1
line4"""
        assert new_content == expected
    
    def test_apply_multiple_hunks(self, temp_dir):
        """Test applying multiple hunks."""
        file_path = os.path.join(temp_dir, "test.py")
        original_content = """line1
line2
line3
line4
line5
line6"""
        
        with open(file_path, 'w') as f:
            f.write(original_content)
        
        hunks = [
            DiffHunk(
                old_start=1,
                old_count=2,
                new_start=1,
                new_count=2,
                diff_lines=[
                    '-line1',
                    '+line1_modified',
                    ' line2'
                ]
            ),
            DiffHunk(
                old_start=5,
                old_count=2,
                new_start=5,
                new_count=2,
                diff_lines=[
                    ' line5',
                    '-line6',
                    '+line6_modified'
                ]
            )
        ]
        
        success, message = apply_diff_to_file(file_path, hunks, temp_dir)
        
        assert success is True
        assert "2 hunk" in message
        
        with open(file_path, 'r') as f:
            new_content = f.read()
        
        expected = """line1_modified
line2
line3
line4
line5
line6_modified"""
        assert new_content == expected
    
    def test_apply_invalid_diff(self, temp_dir):
        """Test that invalid diff doesn't modify file."""
        file_path = os.path.join(temp_dir, "test.py")
        original_content = """line1
line2
line3"""
        
        with open(file_path, 'w') as f:
            f.write(original_content)
        
        # Create invalid hunk (context doesn't match)
        hunks = [
            DiffHunk(
                old_start=1,
                old_count=3,
                new_start=1,
                new_count=3,
                diff_lines=[
                    ' line1',
                    '-wrong_line',  # Doesn't match
                    '+replacement',
                    ' line3'
                ]
            )
        ]
        
        success, message = apply_diff_to_file(file_path, hunks, temp_dir)
        
        assert success is False
        assert "validation failed" in message.lower()
        
        # Verify file wasn't modified
        with open(file_path, 'r') as f:
            content = f.read()
        
        assert content == original_content
    
    def test_apply_preserves_line_ending(self, temp_dir):
        """Test that applying diff preserves trailing newline."""
        file_path = os.path.join(temp_dir, "test.py")
        original_content = """line1
line2
line3
"""  # Note trailing newline
        
        with open(file_path, 'w') as f:
            f.write(original_content)
        
        hunks = [
            DiffHunk(
                old_start=2,
                old_count=1,
                new_start=2,
                new_count=1,
                diff_lines=[
                    '-line2',
                    '+line2_modified'
                ]
            )
        ]
        
        success, message = apply_diff_to_file(file_path, hunks, temp_dir)
        
        assert success is True
        
        with open(file_path, 'r') as f:
            new_content = f.read()
        
        # Should preserve trailing newline
        assert new_content.endswith('\n')
    
    def test_apply_file_not_found(self, temp_dir):
        """Test error when file doesn't exist."""
        file_path = os.path.join(temp_dir, "nonexistent.py")
        
        hunks = [
            DiffHunk(
                old_start=1,
                old_count=1,
                new_start=1,
                new_count=1,
                diff_lines=['-old', '+new']
            )
        ]
        
        success, message = apply_diff_to_file(file_path, hunks, temp_dir)
        
        assert success is False
        assert "does not exist" in message
    
    def test_apply_outside_working_dir(self, temp_dir):
        """Test error when file is outside working directory."""
        # Create a file outside temp_dir
        outside_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py')
        outside_file.write("line1\n")
        outside_file.close()
        
        try:
            hunks = [
                DiffHunk(
                    old_start=1,
                    old_count=1,
                    new_start=1,
                    new_count=1,
                    diff_lines=['-line1', '+line2']
                )
            ]
            
            success, message = apply_diff_to_file(outside_file.name, hunks, temp_dir)
            
            assert success is False
            assert "outside working directory" in message
        finally:
            os.unlink(outside_file.name)


class TestIntegration:
    """Integration tests combining parse and apply operations."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    def test_full_workflow(self, temp_dir):
        """Test complete workflow: parse diff and apply to file."""
        # Create original file
        file_path = os.path.join(temp_dir, "example.py")
        original = """def hello():
    print("hello")
    return 42

def goodbye():
    print("bye")
    return 0
"""
        
        with open(file_path, 'w') as f:
            f.write(original)
        
        # Create a unified diff
        diff = """--- example.py
+++ example.py
@@ -1,4 +1,4 @@
 def hello():
-    print("hello")
+    print("Hello, World!")
     return 42
 
@@ -5,3 +5,3 @@
 def goodbye():
-    print("bye")
+    print("Goodbye, World!")
     return 0
"""
        
        # Parse the diff
        hunks = parse_unified_diff(diff)
        assert len(hunks) == 2
        
        # Apply the diff
        success, message = apply_diff_to_file(file_path, hunks, temp_dir)
        assert success is True
        
        # Verify result
        with open(file_path, 'r') as f:
            result = f.read()
        
        expected = """def hello():
    print("Hello, World!")
    return 42

def goodbye():
    print("Goodbye, World!")
    return 0
"""
        assert result == expected
