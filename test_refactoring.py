"""
Simple test to verify the refactored main.py structure.
Tests that modules can be imported and basic structure is sound.
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Constants for line count testing
ORIGINAL_LINE_COUNT = 2583
REDUCTION_TARGET = 2200  # At least 15% reduction target


def test_import_cli_modules():
    """Test that all new CLI modules can be imported."""
    try:
        from src.cli.initialization import CLIInitializer
        from src.cli.dispatcher import CommandDispatcher
        from src.cli.commands import basic, working_dir, session, mcp, model
        print("✓ All CLI modules imported successfully")
        return True
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False

def test_main_py_parseable():
    """Test that main.py can be parsed as valid Python."""
    import ast
    try:
        with open('main.py', 'r') as f:
            ast.parse(f.read())
        print("✓ main.py is valid Python")
        return True
    except SyntaxError as e:
        print(f"✗ main.py has syntax errors: {e}")
        return False

def test_line_count_reduced():
    """Test that main.py has been reduced in size."""
    with open('main.py', 'r') as f:
        lines = len(f.readlines())
    
    if lines < REDUCTION_TARGET:
        reduction_pct = ((ORIGINAL_LINE_COUNT - lines) / ORIGINAL_LINE_COUNT) * 100
        print(f"✓ main.py reduced from {ORIGINAL_LINE_COUNT} to {lines} lines ({reduction_pct:.1f}% reduction)")
        return True
    else:
        print(f"✗ main.py only reduced to {lines} lines (target: <{REDUCTION_TARGET})")
        return False

def test_documentation_exists():
    """Test that documentation was created."""
    doc_path = 'docs/main.py.md'
    if os.path.exists(doc_path):
        print(f"✓ Documentation exists at {doc_path}")
        return True
    else:
        print(f"✗ Documentation missing at {doc_path}")
        return False

def test_command_modules_exist():
    """Test that command handler modules exist."""
    modules = [
        'src/cli/commands/basic.py',
        'src/cli/commands/working_dir.py',
        'src/cli/commands/session.py',
        'src/cli/commands/mcp.py',
        'src/cli/commands/model.py',
    ]
    
    all_exist = True
    for module in modules:
        if os.path.exists(module):
            print(f"✓ {module} exists")
        else:
            print(f"✗ {module} missing")
            all_exist = False
    
    return all_exist

if __name__ == '__main__':
    print("=" * 60)
    print("Testing refactored main.py structure")
    print("=" * 60)
    
    tests = [
        ("Import CLI modules", test_import_cli_modules),
        ("main.py parseable", test_main_py_parseable),
        ("Line count reduced", test_line_count_reduced),
        ("Documentation exists", test_documentation_exists),
        ("Command modules exist", test_command_modules_exist),
    ]
    
    results = []
    for name, test_func in tests:
        print(f"\n{name}:")
        results.append(test_func())
    
    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Tests: {passed}/{total} passed")
    print("=" * 60)
    
    sys.exit(0 if passed == total else 1)
