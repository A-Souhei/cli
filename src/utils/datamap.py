"""Data mapping functionality for the AI CLI."""

import json
import os
from pathlib import Path

# Import REPOMAP_EXCLUDE_DIRS from repomap module
from .repomap import REPOMAP_EXCLUDE_DIRS


# Constants for datamap functionality
MAX_DATA_SAMPLE_ROWS = 5  # Maximum number of sample rows to include in signature
TYPE_INFERENCE_EXTRA_ROWS = 100  # Extra rows to read for accurate type inference

# Data file extensions to include in datamap
DATA_FILE_EXTENSIONS = {
    '.csv', '.json', '.xlsx', '.xls', '.parquet', '.feather', '.jsonl'
}

# Directories to exclude from datamap scanning (same as repomap)
DATAMAP_EXCLUDE_DIRS = REPOMAP_EXCLUDE_DIRS


def get_data_source_signature(file_path: str, working_dir: str) -> dict:
    """
    Extract the signature of a data file (CSV, JSON, Excel).
    
    The signature contains:
    - column_names: List of column names
    - column_types: Dict mapping column names to their inferred types
    - num_rows: Number of rows
    - num_columns: Number of columns
    - sample_data: First few rows as sample
    - file_size: Size of the file in bytes
    
    Args:
        file_path: Path to the data file (relative or absolute)
        working_dir: Working directory for relative paths
        
    Returns:
        Dict with signature information
    """
    import pandas as pd
    
    # Resolve full path
    if not os.path.isabs(file_path):
        full_path = os.path.join(working_dir, file_path)
    else:
        full_path = file_path
    
    path_obj = Path(full_path)
    if not path_obj.exists():
        return {'error': f'File not found: {file_path}'}
    
    signature = {
        'path': file_path,
        'file_size': path_obj.stat().st_size,
        'extension': path_obj.suffix.lower()
    }
    
    try:
        # Read data based on file type
        ext = path_obj.suffix.lower()
        
        if ext == '.csv':
            df = pd.read_csv(full_path, nrows=MAX_DATA_SAMPLE_ROWS + TYPE_INFERENCE_EXTRA_ROWS)
        elif ext == '.json':
            # Try to read as regular JSON first, then as JSON lines
            try:
                df = pd.read_json(full_path)
            except ValueError:
                df = pd.read_json(full_path, lines=True, nrows=MAX_DATA_SAMPLE_ROWS + TYPE_INFERENCE_EXTRA_ROWS)
        elif ext == '.jsonl':
            df = pd.read_json(full_path, lines=True, nrows=MAX_DATA_SAMPLE_ROWS + TYPE_INFERENCE_EXTRA_ROWS)
        elif ext in ['.xlsx', '.xls']:
            df = pd.read_excel(full_path, nrows=MAX_DATA_SAMPLE_ROWS + TYPE_INFERENCE_EXTRA_ROWS)
        elif ext == '.parquet':
            df = pd.read_parquet(full_path)
            df = df.head(MAX_DATA_SAMPLE_ROWS + TYPE_INFERENCE_EXTRA_ROWS)
        elif ext == '.feather':
            df = pd.read_feather(full_path)
            df = df.head(MAX_DATA_SAMPLE_ROWS + TYPE_INFERENCE_EXTRA_ROWS)
        else:
            return {'error': f'Unsupported file type: {ext}', 'path': file_path}
        
        # For full row count, we need to count separately for large files
        if ext == '.csv':
            try:
                full_df = pd.read_csv(full_path)
                num_rows = len(full_df)
            except Exception:
                num_rows = len(df)  # Fallback to what we read
        elif ext == '.json':
            try:
                full_df = pd.read_json(full_path)
                num_rows = len(full_df)
            except Exception:
                try:
                    full_df = pd.read_json(full_path, lines=True)
                    num_rows = len(full_df)
                except Exception:
                    num_rows = len(df)
        elif ext == '.jsonl':
            try:
                full_df = pd.read_json(full_path, lines=True)
                num_rows = len(full_df)
            except Exception:
                num_rows = len(df)
        elif ext in ['.xlsx', '.xls']:
            try:
                full_df = pd.read_excel(full_path)
                num_rows = len(full_df)
            except Exception:
                num_rows = len(df)
        else:
            num_rows = len(df)
        
        # Extract column information
        signature['column_names'] = df.columns.tolist()
        signature['num_columns'] = len(df.columns)
        signature['num_rows'] = num_rows
        
        # Get column types
        column_types = {}
        for col in df.columns:
            dtype = str(df[col].dtype)
            # Simplify type names for LLM
            if 'int' in dtype:
                column_types[col] = 'integer'
            elif 'float' in dtype:
                column_types[col] = 'float'
            elif 'bool' in dtype:
                column_types[col] = 'boolean'
            elif 'datetime' in dtype:
                column_types[col] = 'datetime'
            elif 'object' in dtype:
                column_types[col] = 'string'
            else:
                column_types[col] = dtype
        
        signature['column_types'] = column_types
        
        # Get sample data (first few rows)
        sample_df = df.head(MAX_DATA_SAMPLE_ROWS)
        signature['sample_data'] = sample_df.to_dict(orient='records')
        
        # Get basic statistics for numeric columns
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        if numeric_cols:
            stats = {}
            for col in numeric_cols:
                stats[col] = {
                    'min': float(df[col].min()) if not pd.isna(df[col].min()) else None,
                    'max': float(df[col].max()) if not pd.isna(df[col].max()) else None,
                    'mean': float(df[col].mean()) if not pd.isna(df[col].mean()) else None
                }
            signature['numeric_stats'] = stats
        
        # Get null counts
        null_counts = df.isnull().sum().to_dict()
        signature['null_counts'] = {k: int(v) for k, v in null_counts.items()}
        
    except Exception as e:
        signature['error'] = str(e)
    
    return signature


def get_postgresql_signature(connection_string: str) -> dict:
    """
    Extract the signature of a PostgreSQL database.
    
    Connection string format: username:password@host:port/database
    or just: username:password@host:port (to list all databases)
    
    Args:
        connection_string: PostgreSQL connection string
        
    Returns:
        Dict with database signature information
    """
    import re
    
    # Parse connection string
    # Format: username:password@host:port/database or username:password@host:port
    match = re.match(r'^([^:]+):([^@]+)@([^:]+):(\d+)(?:/(.+))?$', connection_string)
    if not match:
        return {'error': f'Invalid connection string format. Expected: username:password@host:port/database'}
    
    username, password, host, port, database = match.groups()
    port = int(port)
    
    signature = {
        'host': host,
        'port': port,
        'database': database or 'all',
        'tables': []
    }
    
    try:
        import psycopg2
        
        # Connect to PostgreSQL
        if database:
            conn = psycopg2.connect(
                host=host,
                port=port,
                user=username,
                password=password,
                database=database
            )
        else:
            # Connect to default 'postgres' database to list all databases
            conn = psycopg2.connect(
                host=host,
                port=port,
                user=username,
                password=password,
                database='postgres'
            )
        
        cursor = conn.cursor()
        
        if not database:
            # List all databases
            cursor.execute("SELECT datname FROM pg_database WHERE datistemplate = false;")
            databases = [row[0] for row in cursor.fetchall()]
            signature['databases'] = databases
            conn.close()
            
            # Get signature for each database
            all_db_signatures = []
            for db_name in databases:
                try:
                    db_conn = psycopg2.connect(
                        host=host,
                        port=port,
                        user=username,
                        password=password,
                        database=db_name
                    )
                    db_cursor = db_conn.cursor()
                    db_sig = _get_db_tables_signature(db_cursor, db_name)
                    all_db_signatures.append(db_sig)
                    db_conn.close()
                except Exception as e:
                    all_db_signatures.append({
                        'database': db_name,
                        'error': str(e)
                    })
            
            signature['database_signatures'] = all_db_signatures
        else:
            # Get tables for specific database
            db_sig = _get_db_tables_signature(cursor, database)
            signature['tables'] = db_sig.get('tables', [])
            conn.close()
            
    except ImportError:
        signature['error'] = 'psycopg2 is not installed. Install with: pip install psycopg2-binary'
    except Exception as e:
        signature['error'] = str(e)
    
    return signature


def _get_db_tables_signature(cursor, database_name: str) -> dict:
    """
    Get signature for tables in a database.
    
    Args:
        cursor: Database cursor
        database_name: Name of the database
        
    Returns:
        Dict with tables information
    """
    result = {
        'database': database_name,
        'tables': []
    }
    
    # Get all tables in the public schema
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name;
    """)
    tables = [row[0] for row in cursor.fetchall()]
    
    for table_name in tables:
        table_info = {
            'name': table_name,
            'columns': [],
            'column_types': {}
        }
        
        # Get column information
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            ORDER BY ordinal_position;
        """, (table_name,))
        
        columns = cursor.fetchall()
        for col_name, data_type, is_nullable, col_default in columns:
            table_info['columns'].append(col_name)
            table_info['column_types'][col_name] = {
                'type': data_type,
                'nullable': is_nullable == 'YES',
                'default': col_default
            }
        
        table_info['num_columns'] = len(columns)
        
        # Get row count - use psycopg2.sql for safe identifier quoting
        try:
            from psycopg2 import sql
            cursor.execute(
                sql.SQL('SELECT COUNT(*) FROM {}').format(sql.Identifier(table_name))
            )
            table_info['num_rows'] = cursor.fetchone()[0]
        except Exception:
            table_info['num_rows'] = 'unknown'
        
        # Get sample data (first few rows) - use psycopg2.sql for safe identifier quoting
        try:
            from psycopg2 import sql
            cursor.execute(
                sql.SQL('SELECT * FROM {} LIMIT %s').format(sql.Identifier(table_name)),
                (MAX_DATA_SAMPLE_ROWS,)
            )
            rows = cursor.fetchall()
            sample_data = []
            for row in rows:
                row_dict = {}
                for i, col_name in enumerate(table_info['columns']):
                    val = row[i]
                    # Convert to JSON-serializable format
                    if hasattr(val, 'isoformat'):
                        val = val.isoformat()
                    elif isinstance(val, bytes):
                        val = '<binary data>'
                    row_dict[col_name] = val
                sample_data.append(row_dict)
            table_info['sample_data'] = sample_data
        except Exception as e:
            table_info['sample_error'] = str(e)
        
        result['tables'].append(table_info)
    
    return result


def collect_data_files(working_dir: str, max_files: int = 100) -> list:
    """
    Collect all data files (CSV, JSON, Excel) from the working directory.
    
    Args:
        working_dir: Root directory to scan
        max_files: Maximum number of files to collect
        
    Returns:
        List of dicts with data file signatures
    """
    files = []
    working_path = Path(working_dir)
    
    for file_path in working_path.rglob('*'):
        # Check if we've reached the limit
        if len(files) >= max_files:
            break
            
        # Skip directories in exclusion list
        if any(excluded in file_path.parts[:-1] for excluded in DATAMAP_EXCLUDE_DIRS):
            continue
        
        # Skip non-files
        if not file_path.is_file():
            continue
            
        # Check if file matches data file extensions
        if file_path.suffix.lower() in DATA_FILE_EXTENSIONS:
            relative_path = file_path.relative_to(working_path)
            signature = get_data_source_signature(str(relative_path), working_dir)
            files.append(signature)
                
    return files


def generate_datamap_prompt(data_sources: list, pg_signature: dict = None, code_files: list = None, tree_output: str = None) -> str:
    """
    Generate an LLM prompt to create a comprehensive data map.
    
    Args:
        data_sources: List of data file signatures
        pg_signature: Optional PostgreSQL database signature
        code_files: Optional list of code files for cross-reference
        tree_output: Optional directory tree string to include
        
    Returns:
        Prompt string for the LLM
    """
    # Build data source summaries
    source_summaries = []
    
    # Process file-based data sources
    for source in data_sources:
        if 'error' in source:
            source_summaries.append(f"### {source.get('path', 'Unknown')} (Error: {source['error']})")
            continue
            
        summary_parts = [f"### {source['path']}"]
        summary_parts.append(f"- **Type**: {source['extension']}")
        summary_parts.append(f"- **Size**: {source['file_size']:,} bytes")
        summary_parts.append(f"- **Rows**: {source['num_rows']:,}")
        summary_parts.append(f"- **Columns**: {source['num_columns']}")
        
        # Column details
        summary_parts.append("\n**Columns:**")
        for col_name, col_type in source.get('column_types', {}).items():
            null_count = source.get('null_counts', {}).get(col_name, 0)
            null_info = f" (nulls: {null_count})" if null_count > 0 else ""
            summary_parts.append(f"  - `{col_name}`: {col_type}{null_info}")
        
        # Numeric stats if available
        if 'numeric_stats' in source:
            summary_parts.append("\n**Numeric Statistics:**")
            for col_name, stats in source['numeric_stats'].items():
                mean_val = stats.get('mean')
                if mean_val is not None:
                    stat_line = f"  - `{col_name}`: min={stats['min']}, max={stats['max']}, mean={mean_val:.2f}"
                else:
                    stat_line = f"  - `{col_name}`: min={stats['min']}, max={stats['max']}"
                summary_parts.append(stat_line)
        
        # Sample data
        if 'sample_data' in source and source['sample_data']:
            summary_parts.append("\n**Sample Data (first rows):**")
            summary_parts.append("```json")
            summary_parts.append(json.dumps(source['sample_data'][:3], indent=2, default=str))
            summary_parts.append("```")
        
        source_summaries.append('\n'.join(summary_parts))
    
    # Process PostgreSQL database if provided
    pg_section = ""
    if pg_signature:
        if 'error' in pg_signature:
            pg_section = f"\n## PostgreSQL Database (Error: {pg_signature['error']})\n"
        else:
            pg_parts = ["\n## PostgreSQL Database"]
            pg_parts.append(f"- **Host**: {pg_signature['host']}:{pg_signature['port']}")
            
            if 'database_signatures' in pg_signature:
                # Multiple databases
                for db_sig in pg_signature['database_signatures']:
                    if 'error' in db_sig:
                        pg_parts.append(f"\n### Database: {db_sig['database']} (Error: {db_sig['error']})")
                        continue
                        
                    pg_parts.append(f"\n### Database: {db_sig['database']}")
                    for table in db_sig.get('tables', []):
                        pg_parts.append(f"\n#### Table: `{table['name']}`")
                        pg_parts.append(f"- **Rows**: {table['num_rows']}")
                        pg_parts.append(f"- **Columns**: {table['num_columns']}")
                        pg_parts.append("\n**Schema:**")
                        for col_name in table['columns']:
                            col_info = table['column_types'].get(col_name, {})
                            nullable = " (nullable)" if col_info.get('nullable') else ""
                            pg_parts.append(f"  - `{col_name}`: {col_info.get('type', 'unknown')}{nullable}")
            else:
                # Single database
                for table in pg_signature.get('tables', []):
                    pg_parts.append(f"\n### Table: `{table['name']}`")
                    pg_parts.append(f"- **Rows**: {table['num_rows']}")
                    pg_parts.append(f"- **Columns**: {table['num_columns']}")
                    pg_parts.append("\n**Schema:**")
                    for col_name in table['columns']:
                        col_info = table['column_types'].get(col_name, {})
                        nullable = " (nullable)" if col_info.get('nullable') else ""
                        pg_parts.append(f"  - `{col_name}`: {col_info.get('type', 'unknown')}{nullable}")
                    
                    if 'sample_data' in table:
                        pg_parts.append("\n**Sample Data:**")
                        pg_parts.append("```json")
                        pg_parts.append(json.dumps(table['sample_data'][:3], indent=2, default=str))
                        pg_parts.append("```")
            
            pg_section = '\n'.join(pg_parts)
    
    # Build code files section for cross-reference
    code_section = ""
    if code_files:
        code_parts = ["\n## Related Code Files"]
        code_parts.append("\nThese are code files in the working directory that may use the data sources:")
        for code_file in code_files[:20]:  # Limit to 20 files
            code_parts.append(f"- `{code_file['path']}` ({code_file['size']:,} bytes)")
        code_section = '\n'.join(code_parts)
    
    # Build tree section if provided
    tree_section = ""
    if tree_output:
        tree_section = f"""## Directory Tree

```
{tree_output}
```

"""
    
    # Join data source summaries
    data_content = '\n\n'.join(source_summaries) if source_summaries else "No data files found."
    
    prompt = f"""You are a data analyst creating a comprehensive data map for a project. Analyze the following data sources and create a detailed data map that will help developers understand and work with the data.

{tree_section}## Data Files in Working Directory

{data_content}
{pg_section}
{code_section}

## Instructions

Create a detailed data map with these sections:

1. **Data Overview**:
   - Summary of all data sources available
   - Total number of files and their types
   - Estimated total data volume

2. **Data Schema Summary**:
   - For each data source, describe its structure
   - Highlight key columns and their purposes
   - Note any patterns in column naming

3. **Data Quality Notes**:
   - Note any columns with null values
   - Identify potential data type issues
   - Flag any inconsistencies observed

4. **Relationships**:
   - Identify potential relationships between data sources
   - Note any foreign key-like columns
   - Suggest possible joins or connections

5. **Usage Recommendations**:
   - Suggest which data source to use for common tasks
   - Recommend data transformations that may be needed
   - Note any preprocessing requirements

6. **Code Integration**:
   - For each data source, note which code files might use it
   - Suggest how to load and process each data type
   - Provide example code patterns

Please provide a clear, well-structured data map in Markdown format."""

    return prompt


async def load_datamap_to_context(mcp_client, datamap_path: str, working_dir: str, session_id: str = None) -> dict:
    """
    Load a .datamap file into context using the MCP client.
    
    Args:
        mcp_client: MCPClient instance
        datamap_path: Path to the .datamap file
        working_dir: Working directory
        session_id: Optional session ID for persistence
        
    Returns:
        Result dict with status and message
    """
    args = {
        'file_path': datamap_path,
        'working_dir': working_dir
    }
    if session_id:
        args['session_id'] = session_id
        
    result = await mcp_client.call_tool('coder', 'add_file_context', args)
    
    try:
        return json.loads(result) if result else {'status': 'error', 'message': 'MCP tool returned empty result'}
    except json.JSONDecodeError as parse_error:
        # Provide more specific error information with type safety
        result_str = str(result) if result is not None else ''
        error_preview = (result_str[:100] + '...') if len(result_str) > 100 else result_str
        return {'status': 'error', 'message': f'Failed to parse response: {parse_error}. Response: {error_preview}'}
