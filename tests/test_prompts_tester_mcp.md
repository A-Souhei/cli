# Test Prompts for Tester MCP

This file contains test prompts to validate the tester MCP's plan_mode functionality.

## Basic Plan Mode Test

### Prompt 1: Simple Plan and Test Workflow
```
I need to plan and test a simple calculator. Create a calculator.py file with add and subtract functions, then create tests for it and run them.
```

**Expected Behavior:**
- Detects keywords: "plan", "test"
- Creates execution plan with steps
- Matches tools: write_python_code, create_pytest_test, run_pytest
- Generates TODO list with tool assignments

### Prompt 2: Plan with Validation
```
Plan to create a fibonacci function and validate it with unit tests
```

**Expected Behavior:**
- Generates plan for:
  1. Creating Python file
  2. Writing test file
  3. Running pytest validation

### Prompt 3: Testing Keyword Variations
```
I want to test my code: create sorting.py with bubble sort, write tests, and validate
```

**Expected Behavior:**
- Detects "test" and "validate" keywords
- Creates comprehensive execution plan

## Advanced Plan Mode Test

### Prompt 4: Multi-Step Plan
```
Plan and test a complete workflow: 
1. Create a user class in models/user.py
2. Add validation methods
3. Create comprehensive tests
4. Run pytest with coverage
```

**Expected Behavior:**
- Breaks down into discrete steps
- Matches each step with appropriate tools
- Includes test creation and execution

### Prompt 5: Plan with File References
```
Plan to update @calculator.py with multiply function and test it
```

**Expected Behavior:**
- Detects file reference
- Plans to edit existing file
- Creates test and validates

## Testing Tools Only

### Prompt 6: Run Pytest
```
Run tests in tests/test_calculator.py
```

**Expected Behavior:**
- Uses run_pytest tool directly
- Shows verbose output

### Prompt 7: Create Test Template
```
Create a test file for my validator module
```

**Expected Behavior:**
- Uses create_pytest_test tool
- Generates test template with fixtures

### Prompt 8: Validate Code
```
Validate calculator.py with its tests
```

**Expected Behavior:**
- Uses validate_with_test tool
- Runs tests and reports pass/fail

## Expected Keywords Detection

The plan_mode tool should be triggered by these keywords:
- "plan"
- "test"
- "testing"
- "validate"
- "plan and test"
- "create and test"
- "build and validate"

## Tool Matching Expected Results

When plan_mode analyzes a prompt like:
> "Plan to create calculator.py with add function and test it"

Expected execution plan:
1. **Step 1:** "Create calculator.py with add function"
   - **Tool:** write_python_code
   - **MCP:** coder

2. **Step 2:** "Create test file for calculator"
   - **Tool:** create_pytest_test
   - **MCP:** tester

3. **Step 3:** "Run the tests"
   - **Tool:** run_pytest
   - **MCP:** tester

4. **Step 4:** "Validate the implementation"
   - **Tool:** validate_with_test
   - **MCP:** tester
