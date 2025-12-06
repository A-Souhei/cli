# /code Mode Test Prompts

This document contains test prompts to validate the `/code` mode context accumulation feature.

## Overview

The `/code` mode now accumulates context from previous steps, allowing the LLM to see files loaded in earlier steps when generating code in later steps.

**Key Feature**: When using tools like `add_file_context` or `add_directory_context` in earlier steps, the loaded file contents are passed as reference material to subsequent code generation steps.

---

## Test Setup

Before running tests, ensure:
1. You're in the project root directory
2. The test files in `testing/python_app/` are in their original state
3. Run `git checkout -- testing/python_app/` to reset if needed

After each test, restore files: `git checkout -- testing/python_app/`

---

## Test 1: Basic Import - Single File Context ✅

**Status**: Already validated manually

**Objective**: Import a function from one file into another

**Prompt**:
```
/code Import validate_email from @utils/helpers.py into @services/user_service.py and use it in the UserService.create_user method to validate email before creating a user.
```

**Expected Steps**:
1. Load `utils/helpers.py` into context using `add_file_context`
2. Load `services/user_service.py` into context using `add_file_context`
3. Edit `services/user_service.py` to import and use `validate_email`

**Success Criteria**:
- ✅ Import statement: `from utils.helpers import validate_email`
- ✅ Validation call in `create_user`: `if not validate_email(email): raise ValueError(...)`
- ✅ No git diff format output
- ✅ Complete file output with all original functions preserved

**Restore**:
```bash
git checkout -- testing/python_app/services/user_service.py
```

---

## Test 2: Multi-File Context (3+ files)

**Objective**: Use functions from multiple files loaded in context

**Prompt**:
```
/code Load @utils/helpers.py and @models/product.py. Then in @services/product_service.py create_product method, add validation that uses calculate_percentage from helpers to check that the discount is between 0 and 100 percent.
```

**Expected Steps**:
1. Load `utils/helpers.py` (contains `calculate_percentage`)
2. Load `models/product.py` (contains `Product` class)
3. Load `services/product_service.py`
4. Edit `product_service.py` to import and use `calculate_percentage`

**Success Criteria**:
- ✅ Import: `from ..utils.helpers import calculate_percentage` or `from utils.helpers import calculate_percentage`
- ✅ Validation in `create_product` method using `calculate_percentage`
- ✅ All existing methods in `product_service.py` preserved

**Restore**:
```bash
git checkout -- testing/python_app/services/product_service.py
```

---

## Test 3: Cross-Model Reference

**Objective**: Copy a method pattern from one model to another

**Prompt**:
```
/code Load @models/user.py to see the from_dict classmethod pattern. Then add a similar from_dict classmethod to @models/product.py that creates a Product from a dictionary.
```

**Expected Steps**:
1. Load `models/user.py` (see `from_dict` pattern)
2. Load `models/product.py`
3. Edit `models/product.py` to add `from_dict` classmethod

**Success Criteria**:
- ✅ `@classmethod` decorator added
- ✅ `from_dict(cls, data: dict) -> 'Product'` method signature
- ✅ Method creates Product from dict keys: id, name, price, stock, discount
- ✅ All existing methods preserved

**Restore**:
```bash
git checkout -- testing/python_app/models/product.py
```

---

## Test 4: Directory Context

**Objective**: Load entire directory and reference multiple files

**Prompt**:
```
/code Load @utils directory. Then add a new function format_percentage in @utils/helpers.py that takes a number and returns it formatted as a percentage string (e.g., 15.5 becomes "15.5%").
```

**Expected Steps**:
1. Load entire `utils/` directory using `add_directory_context`
2. Load `utils/helpers.py`
3. Edit `utils/helpers.py` to add `format_percentage` function

**Success Criteria**:
- ✅ New function `format_percentage(value: float) -> str` added
- ✅ Returns string with % sign (e.g., `f"{value}%"`)
- ✅ All existing functions (`format_currency`, `validate_email`, `calculate_percentage`) preserved

**Restore**:
```bash
git checkout -- testing/python_app/utils/helpers.py
```

---

## Test 5: Error Handling - Missing File

**Objective**: Verify graceful handling when file doesn't exist

**Prompt**:
```
/code Import non_existent_function from @utils/missing.py into @services/user_service.py
```

**Expected Behavior**:
- Step 1 should fail with error: "File not found" or "Error reading file"
- CLI should NOT crash
- Error should be displayed clearly
- No changes should be made to any files

**Success Criteria**:
- ✅ Error message displayed for missing file
- ✅ CLI continues running (no crash)
- ✅ No files modified
- ✅ User can continue with other commands

**Restore**: Not needed (no changes expected)

---

## Test 6: No Context Leakage

**Objective**: Ensure reference section headers don't appear in generated code

**Prompt**:
```
/code Load @utils/helpers.py for reference. Then add a module docstring to @services/user_service.py that says "User service with validation support."
```

**Expected Steps**:
1. Load `utils/helpers.py` (for context)
2. Load `services/user_service.py`
3. Edit `services/user_service.py` to add module docstring

**Success Criteria**:
- ✅ Module docstring added: `"""User service with validation support."""`
- ✅ NO reference section text in output: `Reference File:`
- ✅ NO reference markers: `=== REFERENCE ===` or `=== END REFERENCE ===`
- ✅ Clean Python code output only

**Verify**:
```bash
# Should NOT find these patterns:
grep -i "reference file" testing/python_app/services/user_service.py
grep -i "=== REFERENCE" testing/python_app/services/user_service.py
# Both should return no results
```

**Restore**:
```bash
git checkout -- testing/python_app/services/user_service.py
```

---

## Test 7: Sequential Context Build-Up

**Objective**: Verify context accumulates across all steps (Step 1 + Step 2 available in Step 3)

**Prompt**:
```
/code Load @utils/helpers.py, then load @models/user.py, then add a validate_name method to @models/product.py that follows a similar validation pattern to what you saw in User model and helpers.
```

**Expected Steps**:
1. Load `utils/helpers.py` (see validation pattern with `validate_email`)
2. Load `models/user.py` (see validation in `__post_init__`)
3. Load `models/product.py`
4. Edit `models/product.py` to add `validate_name` method

**Success Criteria**:
- ✅ New `validate_name` method added to Product class
- ✅ Method follows validation pattern (similar structure to `validate_email`)
- ✅ Method validates product name (e.g., not empty, reasonable length)
- ✅ All existing methods preserved

**Restore**:
```bash
git checkout -- testing/python_app/models/product.py
```

---

## Test 8: Complex Multi-Step Refactoring

**Objective**: Test complex workflow with multiple edits

**Prompt**:
```
/code Load @utils/helpers.py to see validate_email. Then create a new file @utils/validators.py and move the validate_email function there. Then update the import in @models/user.py from utils.helpers to utils.validators.
```

**Expected Steps**:
1. Load `utils/helpers.py`
2. Create `utils/validators.py` with `validate_email` function
3. Load `models/user.py`
4. Edit `models/user.py` to update import statement

**Success Criteria**:
- ✅ New file created: `testing/python_app/utils/validators.py`
- ✅ `validate_email` function in validators.py
- ✅ Import in user.py updated: `from ..utils.validators import validate_email`
- ✅ User model still works correctly

**Restore**:
```bash
rm -f testing/python_app/utils/validators.py
git checkout -- testing/python_app/models/user.py
```

---

## Test 9: Using Context for Method Implementation

**Objective**: Implement a new method by referencing similar methods from context

**Prompt**:
```
/code Load @models/product.py to see the get_final_price method. Then add a get_savings_amount method to @models/product.py that returns how much money is saved when discount is applied (original price minus final price).
```

**Expected Steps**:
1. Load `models/product.py` (see `get_final_price` implementation)
2. Edit `models/product.py` to add `get_savings_amount` method

**Success Criteria**:
- ✅ New method: `def get_savings_amount(self) -> float:`
- ✅ Returns: `self.price - self.get_final_price()`
- ✅ All existing methods preserved
- ✅ Method reuses existing `get_final_price()` logic

**Restore**:
```bash
git checkout -- testing/python_app/models/product.py
```

---

## Test 10: Import with Alias

**Objective**: Test importing with alias/renaming

**Prompt**:
```
/code Load @utils/helpers.py. Then in @services/product_service.py, import format_currency from helpers and use it in the create_product method to log the formatted price.
```

**Expected Steps**:
1. Load `utils/helpers.py` (contains `format_currency`)
2. Load `services/product_service.py`
3. Edit to import and use `format_currency`

**Success Criteria**:
- ✅ Import: `from ..utils.helpers import format_currency` or similar
- ✅ Usage in `create_product`: e.g., `formatted_price = format_currency(price)`
- ✅ All existing functionality preserved

**Restore**:
```bash
git checkout -- testing/python_app/services/product_service.py
```

---

## Validation Checklist

For each test, verify:

- [ ] Context from previous steps is visible in generated code
- [ ] LLM correctly identifies functions/classes from loaded files
- [ ] Import statements use correct paths
- [ ] No git diff format in output (actual Python code only)
- [ ] No reference section headers leaked into code
- [ ] Original docstrings preserved (not simplified)
- [ ] Original code structure preserved (no unwanted refactoring)
- [ ] Line count approximately matches original file
- [ ] All existing methods/functions still present

---

## Known Issues & Expected Behavior

### Minor Acceptable Issues:
- ✅ Comments may be added to new code (e.g., `# Validate email`)
- ✅ Module docstring might be removed (known limitation)
- ✅ Very minor docstring rewording (e.g., "Search query" → "Search term")

### Unacceptable Issues:
- ❌ Git diff format output instead of code
- ❌ Reference section headers in code output
- ❌ Functions removed or significantly refactored
- ❌ Functionality broken or changed
- ❌ Imports from wrong paths

---

## Test Results Template

Use this template to track test results:

```
Test #: [Test Name]
Date: [YYYY-MM-DD]
Status: ✅ PASS / ❌ FAIL / ⚠️ PARTIAL

Prompt Used:
[exact prompt]

Steps Generated:
1. [step 1]
2. [step 2]
3. [step 3]

Results:
- Context Accumulated: [YES/NO]
- Correct Import Path: [YES/NO]
- Code Format: [CLEAN/GIT_DIFF/OTHER]
- Original Code Preserved: [YES/NO]
- Reference Leakage: [YES/NO]

Issues Found:
[list any issues]

Notes:
[additional observations]
```

---

## Troubleshooting

### If context is not accumulating:
1. Check that files are being loaded in earlier steps
2. Verify `add_file_context` tool is being called
3. Look for "Stored context for [file]" in debug output
4. Check `accumulated_file_contexts` dictionary has entries

### If git diff format appears:
1. The prompt rules may need strengthening
2. Check LLM model being used (needs to be coder model)
3. Verify edit prompt includes "NOT a git diff" warning

### If reference headers leak into code:
1. Check context section labeling is clear
2. Verify "DO NOT COPY THIS TEXT" warning is present
3. May need to adjust context section format

---

## Success Metrics

After running all tests:

**Must Pass** (Critical):
- 90%+ tests show context accumulation working
- No reference section leakage
- No git diff format output
- Import paths are correct

**Should Pass** (Important):
- No unwanted refactoring in 80%+ tests
- Docstrings preserved in 80%+ tests
- Line count maintained in 80%+ tests

**Nice to Have** (Minor):
- No explanatory comments added
- Module docstrings preserved
- Perfect preservation of all code style
