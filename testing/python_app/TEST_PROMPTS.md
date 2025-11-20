# Test Prompts for Python App with @ Prefixer

This file contains test prompts to demonstrate the @ prefixer feature with the Python test application.

## Prerequisites

1. Start a session: `session start`
2. Navigate to the testing/python_app directory or use full paths

## Test 1: Add File Context

Test adding a single file to context:

```
@utils/helpers.py explain what this file does
```

Expected behavior:
- File content is read and added to RAG context
- LLM explains the helper functions

## Test 2: Add Directory Context

Test adding entire directory to context:

```
@models/ what models are defined in this directory?
```

Expected behavior:
- All files in models directory are added to context
- LLM describes User and Product models

## Test 3: Create New File

Test creating a new Python file using @ prefix:

```
@config.py create a configuration class with database settings (host, port, user, password) and a method to load from environment variables
```

Expected behavior:
- config.py is created with generated code
- Code includes a Config class with the specified features

## Test 4: Edit Existing File

Test editing an existing file:

```
@utils/helpers.py add a function to calculate the average of a list of numbers
```

Expected behavior:
- The helpers.py file is updated with the new function
- Existing code remains intact

## Test 5: Multi-File Context

Test using multiple files in context:

```
@models/user.py @models/product.py create a new file that defines an Order model that references both User and Product
```

Expected behavior:
- Both model files are added to context
- New Order model is created referencing User and Product

## Test 6: Directory Context for Code Generation

Test using directory context for intelligent code generation:

```
@services/ create a new service called OrderService that manages orders with create, get, and list methods following the same pattern as the existing services
```

Expected behavior:
- All service files are added to context
- OrderService is created following the established patterns

## Test 7: Session Persistence

Test session-based context persistence:

```
# First prompt (in active session)
@models/ add these models to my session context

# Second prompt (same session)
create a report generator that uses the User and Product models
```

Expected behavior:
- First prompt adds models to session context
- Second prompt uses the persisted context without re-specifying @models/

## Test 8: Complex Code Generation

Test generating complex code with multiple context files:

```
@app.py @services/ create a new CLI interface that allows users to interactively create users and products using the existing services
```

Expected behavior:
- App.py and all services are added to context
- New CLI interface is generated that properly uses the services

## Test 9: Non-Existing File with Extension Detection

Test creating files with different extensions:

```
@test_script.py write a pytest test file that tests the UserService create_user method
```

Expected behavior:
- Python code is generated and written to test_script.py
- Code includes proper pytest structure

## Test 10: Refactoring with Context

Test refactoring using context:

```
@models/user.py @models/product.py refactor these models to use a common base class for shared functionality like to_dict and from_dict
```

Expected behavior:
- Both model files are read
- Refactored code is provided
- User can choose which files to update
