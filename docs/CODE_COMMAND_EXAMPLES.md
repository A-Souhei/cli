# /code Command - Example Prompts

This document provides example prompts for the `/code` command that are optimized to match the available coder MCP tools.

## Quick Start

```bash
# Simply use the /code command with any prompt below
# (A session will auto-start if needed)
/code <your prompt here>

# Optional: Start a session manually first
/session start
```

---

## Python Code Execution Examples

### Example 1: Simple Python Script
```bash
/code write a python script that prints hello world and the current date
```
**Matches:** `run_python_code`

**What it does:**
- Generates Python code
- Executes it immediately
- Shows output

---

### Example 2: Data Processing
```bash
/code create python code that generates a list of 10 random numbers, calculates their mean and standard deviation, then prints the results
```
**Matches:** `run_python_code`

**Expected output:**
- Random number generation
- Statistical calculations
- Formatted output

---

### Example 3: File Operations
```bash
/code write a python script that reads all text files in the current directory and counts the total number of lines
```
**Matches:** `run_python_code`

**Use case:** File system operations

---

### Example 4: JSON Processing
```bash
/code create python code that generates a sample JSON object with user data (name, age, email) and pretty prints it
```
**Matches:** `run_python_code`

**Output:** JSON formatted data

---

## R Code Execution Examples

### Example 5: Basic R Statistics
```bash
/code write R code that creates a vector of 20 random normal values and displays summary statistics
```
**Matches:** `run_r_code`

**What it does:**
- Generates random data in R
- Calculates statistics
- Displays results

---

### Example 6: R Data Frame
```bash
/code create R code that builds a data frame with 3 columns (ID, Name, Score) for 5 students and displays it
```
**Matches:** `run_r_code`

**Use case:** Data frame creation and manipulation

---

## File Creation Examples

### Example 7: Create Python Module
```bash
/code create a python file called utils.py with helper functions for string manipulation: reverse_string, capitalize_words, and count_vowels
```
**Matches:** `write_python_code`

**Result:** Creates `utils.py` file

---

### Example 8: Create Data Analysis Script
```bash
/code write a python script named analyze_data.py that contains functions to calculate mean, median, mode, and standard deviation of a list of numbers
```
**Matches:** `write_python_code`

**Result:** Creates `analyze_data.py` with statistical functions

---

### Example 9: Create R Analysis Script
```bash
/code create an R script file called stats_analysis.R with functions for linear regression and correlation analysis
```
**Matches:** `write_r_code`

**Result:** Creates `stats_analysis.R` file

---

## Multi-Step Task Examples

### Example 10: Complete Data Pipeline
```bash
/code create a data analysis pipeline that: generates sample CSV data with 100 rows, reads it back, filters values above 50, calculates statistics, and plots a histogram
```
**Matches Multiple Tools:**
- `write_python_code` (for data generation)
- `run_python_code` (for analysis)

**What happens:**
1. Breaks down into steps
2. Matches appropriate tools
3. Executes in sequence

---

### Example 11: Web Scraping and Analysis
```bash
/code write code that fetches data from a REST API endpoint (use JSONPlaceholder), extracts user information, converts to a pandas DataFrame, and displays the first 5 rows
```
**Matches:** `run_python_code`

**Steps identified:**
1. Fetch API data
2. Parse JSON
3. Create DataFrame
4. Display results

---

### Example 12: File Processing Workflow
```bash
/code create a workflow that: creates a text file with sample log entries, reads and parses the file, filters error messages, counts occurrences, and saves results to a new file
```
**Matches Multiple Tools:**
- `write_python_code` (create file)
- `run_python_code` (process and analyze)

---

## Testing and Validation Examples

### Example 13: Unit Test Generation
```bash
/code write python code that creates a simple calculator class with add, subtract, multiply, divide methods, then write unit tests to verify each method works correctly
```
**Matches:** `run_python_code`

**Result:** Code with built-in tests

---

### Example 14: Data Validation
```bash
/code create python code that validates email addresses using regex, tests it with 5 sample emails (3 valid, 2 invalid), and prints validation results
```
**Matches:** `run_python_code`

**Use case:** Input validation

---

## Visualization Examples

### Example 15: Basic Plotting
```bash
/code write python code using matplotlib to create a line plot of sine wave from 0 to 2π, with proper labels and title, then save it as plot.png
```
**Matches:** `run_python_code`

**Result:**
- Generates plot
- Saves to file
- Shows execution status

---

### Example 16: Multiple Charts
```bash
/code create python code that generates random data and creates 3 subplots: histogram, scatter plot, and bar chart, then saves as dashboard.png
```
**Matches:** `run_python_code`

**Output:** Multi-panel visualization

---

## Database Examples

### Example 17: SQLite Operations
```bash
/code write python code that creates an SQLite database, creates a users table, inserts 5 sample records, queries all records, and displays them
```
**Matches:** `run_python_code`

**Steps:**
1. Create database
2. Define schema
3. Insert data
4. Query and display

---

### Example 18: CSV to Database
```bash
/code create code that generates a CSV file with product data, then reads it and inserts all records into an SQLite database, finally queries and displays the count
```
**Matches Multiple Tools:**
- `write_python_code` (CSV generation)
- `run_python_code` (DB operations)

---

## Text Processing Examples

### Example 19: Text Analysis
```bash
/code write python code that analyzes a sample text paragraph: counts words, sentences, most frequent words, and calculates average word length
```
**Matches:** `run_python_code`

**Analysis includes:**
- Word count
- Sentence count
- Frequency analysis
- Statistics

---

### Example 20: String Manipulation
```bash
/code create python code that demonstrates various string operations: reverse, palindrome check, remove duplicates, and character frequency count on sample text
```
**Matches:** `run_python_code`

---

## API and Network Examples

### Example 21: REST API Client
```bash
/code write python code that makes a GET request to https://api.github.com/users/octocat, parses the JSON response, and displays the name, bio, and public repos count
```
**Matches:** `run_python_code`

**What it does:**
- HTTP request
- JSON parsing
- Data extraction

---

### Example 22: Weather Data
```bash
/code create python code that fetches weather data from wttr.in API for New York, parses the response, and displays current temperature and conditions
```
**Matches:** `run_python_code`

---

## Complex Workflow Examples

### Example 23: ETL Pipeline
```bash
/code build an ETL pipeline that: generates sample sales data with dates and amounts, transforms it by adding calculated fields, filters last 30 days, aggregates by week, and displays summary statistics
```
**Matches:** `run_python_code`

**Pipeline stages:**
1. Extract (generate data)
2. Transform (calculations)
3. Load (aggregate)
4. Report (statistics)

---

### Example 24: Log Analysis System
```bash
/code create a log analysis system that: generates sample application logs with timestamps and severity levels, parses them, counts errors by type, finds patterns, and creates a summary report
```
**Matches:** `run_python_code`

**Components:**
- Log generation
- Parsing
- Analysis
- Reporting

---

### Example 25: Data Quality Check
```bash
/code write code that creates a dataset with intentional quality issues (missing values, duplicates, outliers), then runs quality checks, identifies issues, and generates a quality report
```
**Matches:** `run_python_code`

---

## Machine Learning Examples

### Example 26: Simple Classification
```bash
/code create python code that generates synthetic classification data, splits into train/test, trains a simple decision tree classifier, makes predictions, and displays accuracy
```
**Matches:** `run_python_code`

**ML workflow:**
1. Data generation
2. Train/test split
3. Model training
4. Evaluation

---

### Example 27: Clustering Analysis
```bash
/code write python code that generates 2D random points in 3 clusters, applies K-means clustering, visualizes the results with different colors for each cluster, and saves the plot
```
**Matches:** `run_python_code`

---

## File System Examples

### Example 28: Directory Scanner
```bash
/code create python code that scans the current directory, lists all files with their sizes, calculates total size, groups by file extension, and displays statistics
```
**Matches:** `run_python_code`

**Output:**
- File listing
- Size statistics
- Extension grouping

---

### Example 29: File Organization
```bash
/code write code that creates a sample file structure with multiple text files, scans them, categorizes by size (small/medium/large), and displays the categorization
```
**Matches:** `run_python_code`

---

## Utility Examples

### Example 30: Password Generator
```bash
/code create python code that generates 5 secure random passwords with configurable length (12 chars), including uppercase, lowercase, numbers, and special characters
```
**Matches:** `run_python_code`

---

### Example 31: UUID Generator
```bash
/code write python code that generates 10 UUIDs in different formats (UUID1, UUID4), displays them in a formatted table, and saves to a text file
```
**Matches:** `run_python_code`

---

### Example 32: Date Calculator
```bash
/code create python code that calculates and displays: current date, date 30 days ago, date 90 days from now, number of days until end of year, and current week number
```
**Matches:** `run_python_code`

---

## Best Practices for Prompts

### ✅ Good Prompts

1. **Be Specific About Actions**
   ```bash
   /code write python code that creates a list of 10 random numbers and sorts them
   ```

2. **Include Expected Output**
   ```bash
   /code create code that calculates factorial of 5 and prints the result
   ```

3. **Specify File Operations Clearly**
   ```bash
   /code write a python script named calculator.py with functions for basic math operations
   ```

4. **Break Down Complex Tasks**
   ```bash
   /code build a program that generates sample data, analyzes it, and creates a visualization
   ```

### ❌ Avoid Vague Prompts

1. **Too General**
   ```bash
   /code do something with data
   ```

2. **Missing Context**
   ```bash
   /code analyze this
   ```

3. **Unclear Intent**
   ```bash
   /code make a thing
   ```

---

## Matching Tools Reference

Here's how prompts map to MCP tools:

| Prompt Keywords | Matched Tool | Purpose |
|----------------|--------------|---------|
| "write/create python code" (no file) | `run_python_code` | Execute Python |
| "create file/script named *.py" | `write_python_code` | Create Python file |
| "update/modify file *.py" | `edit_python_code` | Edit Python file |
| "write/create R code" (no file) | `run_r_code` | Execute R code |
| "create R script *.R" | `write_r_code` | Create R file |
| "update R file *.R" | `edit_r_code` | Edit R file |
| Multi-step with "then", "and" | Multiple tools | Chain execution |

---

## Tips for Best Results

1. **Start Simple**: Begin with single-task prompts to understand the flow
2. **Use Sessions**: Always start a session before using `/code`
3. **Be Explicit**: Mention file names if you want files created
4. **Check Output**: Review the instruction sequence before execution
5. **Iterate**: Refine prompts based on results

---

## Troubleshooting

### Prompt doesn't match expected tool
- **Solution**: Be more specific about the action (execute, create, modify)

### Multiple tools matched but not all needed
- **Solution**: Simplify the prompt to focus on one main task

### No tools matched
- **Solution**: Use clearer action verbs (write, create, execute, analyze)

---

## Advanced Usage

### Combining with @ Context
```bash
# Add file context, then analyze
@data.csv /code analyze this CSV file and calculate column statistics
```

### Sequential Workflows
```bash
# Run multiple /code commands in sequence for complex workflows
/code create sample data and save to data.csv
/code read data.csv and create visualizations
/code analyze the results and generate a report
```

---

## See Also

- [/code Command Documentation](./CODE_COMMAND.md)
- [MCP Tools Documentation](./MCP_TOOLS_RETRIEVE_AND_ROLL_THE_DICE.md)
- [Coder MCP Tools](./CODEBASE_EXPLORATION_SUMMARY.md)
