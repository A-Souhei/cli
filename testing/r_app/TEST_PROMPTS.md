# Test Prompts for R App with @ Prefixer

This file contains test prompts to demonstrate the @ prefixer feature with the R test application.

## Prerequisites

1. Start a session: `session start`
2. Navigate to the testing/r_app directory or use full paths
3. Ensure R is installed on your system

## Test 1: Add File Context

Test adding a single R file to context:

```
@utils/helpers.R explain what functions are available in this file
```

Expected behavior:
- File content is read and added to RAG context
- LLM explains the helper functions (format_currency, validate_email, etc.)

## Test 2: Add Directory Context

Test adding entire models directory to context:

```
@models/ describe the data models in this directory and their relationships
```

Expected behavior:
- All R files in models directory are added to context
- LLM describes User and Product models

## Test 3: Create New R File

Test creating a new R file using @ prefix:

```
@config.R create a configuration system with database connection settings and a function to load from environment variables
```

Expected behavior:
- config.R is created with generated R code
- Code includes proper Roxygen documentation
- Follows R coding conventions

## Test 4: Edit Existing File

Test editing an existing R file:

```
@utils/helpers.R add a function to calculate the median of a numeric vector with NA handling
```

Expected behavior:
- The helpers.R file is updated with the new function
- Existing code and documentation remain intact

## Test 5: Multi-File Context

Test using multiple files in context:

```
@models/user.R @models/product.R create a new file that defines an Order model that combines User and Product data
```

Expected behavior:
- Both model files are added to context
- New Order model is created following R conventions
- Includes proper Roxygen documentation

## Test 6: Directory Context for Code Generation

Test using directory context for intelligent code generation:

```
@services/ create a new OrderService that manages orders following the same pattern as UserService and ProductService
```

Expected behavior:
- All service files are added to context
- OrderService is created following established R patterns
- Maintains consistency with existing services

## Test 7: Session Persistence

Test session-based context persistence:

```
# First prompt (in active session)
@models/ @utils/ add these to my session context

# Second prompt (same session)
create a reporting function that generates summary statistics using the models and utility functions
```

Expected behavior:
- First prompt adds models and utils to session context
- Second prompt uses the persisted context
- Generated code properly sources and uses the existing functions

## Test 8: Complex Code Generation with Data Frames

Test generating code that works with R data frames:

```
@app.R @services/ create a function that generates a comprehensive report combining user and product data into a single data frame with visualizations
```

Expected behavior:
- App.R and all services are added to context
- Generated code uses proper data frame operations
- Includes visualization code using base R or ggplot2

## Test 9: Statistical Analysis

Test creating statistical analysis code:

```
@models/product.R create an analysis script that performs statistical analysis on product prices including mean, median, standard deviation, and price distribution visualization
```

Expected behavior:
- Product model is added to context
- Statistical analysis code is generated
- Includes proper R statistical functions

## Test 10: Package-Style Structure

Test creating code following R package conventions:

```
@utils/ @models/ create a DESCRIPTION file and NAMESPACE file to convert this into an R package
```

Expected behavior:
- Utility and model files are analyzed
- DESCRIPTION file is generated with proper package metadata
- NAMESPACE file exports relevant functions

## Test 11: Unit Tests with testthat

Test generating R unit tests:

```
@services/user_service.R create a testthat test file that tests all functions in the UserService
```

Expected behavior:
- UserService code is added to context
- Test file is created using testthat package
- Tests cover all major functions

## Test 12: Documentation Generation

Test creating R documentation:

```
@models/ @services/ generate a comprehensive README.md that documents all models and services with usage examples
```

Expected behavior:
- All model and service files are added to context
- README with proper R code examples
- Includes installation and usage instructions
