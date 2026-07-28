"""Check for duplicate test names within the same class or module.

This test verifies that no test class or module body defines the same test
name more than once, which would result in the first definition being shadowed
by the second in Python.
"""

import ast
import sys
from pathlib import Path


def check_file_for_duplicate_test_names(filepath: str) -> list[str]:
    """Check a test file for duplicate test method names within classes.
    
    Returns a list of error messages describing any duplicates found.
    """
    errors = []
    
    with open(filepath, 'r') as f:
        try:
            tree = ast.parse(f.read(), filename=filepath)
        except SyntaxError as e:
            return [f"{filepath}:{e.lineno}: SyntaxError: {e.msg}"]
    
    for node in ast.walk(tree):
        # Check for duplicate test methods within a class
        if isinstance(node, ast.ClassDef):
            method_names = {}
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name.startswith('test_'):
                    if item.name in method_names:
                        errors.append(
                            f"{filepath}:{item.lineno}: In class {node.name}, "
                            f"duplicate test method '{item.name}' "
                            f"(first defined at line {method_names[item.name]})"
                        )
                    else:
                        method_names[item.name] = item.lineno
        
        # Check for duplicate test functions at module level
        elif isinstance(node, ast.Module):
            func_names = {}
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name.startswith('test_'):
                    if item.name in func_names:
                        errors.append(
                            f"{filepath}:{item.lineno}: At module level, "
                            f"duplicate test function '{item.name}' "
                            f"(first defined at line {func_names[item.name]})"
                        )
                    else:
                        func_names[item.name] = item.lineno
    
    return errors


def test_no_duplicate_test_names_in_test_files():
    """Ensure no test file has shadowed test names."""
    tests_dir = Path(__file__).parent
    test_files = sorted(tests_dir.glob('test_*.py'))
    
    all_errors = []
    for test_file in test_files:
        errors = check_file_for_duplicate_test_names(str(test_file))
        all_errors.extend(errors)
    
    if all_errors:
        error_msg = "Found duplicate test names:\n" + "\n".join(all_errors)
        raise AssertionError(error_msg)
