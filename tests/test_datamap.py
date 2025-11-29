"""Tests for the datamap functionality."""

import pytest
import tempfile
import os
import json
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from main import (
    collect_data_files,
    get_data_source_signature,
    generate_datamap_prompt,
    load_datamap_to_context,
    DATA_FILE_EXTENSIONS,
    DATAMAP_EXCLUDE_DIRS,
    MAX_DATA_SAMPLE_ROWS,
    TYPE_INFERENCE_EXTRA_ROWS,
)


@pytest.mark.unit
class TestDataFileExtensions:
    """Tests for DATA_FILE_EXTENSIONS constant."""

    def test_includes_csv(self):
        """Test that CSV extension is included."""
        assert '.csv' in DATA_FILE_EXTENSIONS

    def test_includes_json(self):
        """Test that JSON extension is included."""
        assert '.json' in DATA_FILE_EXTENSIONS

    def test_includes_excel(self):
        """Test that Excel extensions are included."""
        assert '.xlsx' in DATA_FILE_EXTENSIONS
        assert '.xls' in DATA_FILE_EXTENSIONS

    def test_includes_parquet(self):
        """Test that Parquet extension is included."""
        assert '.parquet' in DATA_FILE_EXTENSIONS

    def test_includes_jsonl(self):
        """Test that JSONL extension is included."""
        assert '.jsonl' in DATA_FILE_EXTENSIONS


@pytest.mark.unit
class TestDatamapExcludeDirs:
    """Tests for DATAMAP_EXCLUDE_DIRS constant."""

    def test_includes_common_excludes(self):
        """Test that common directories to exclude are included."""
        expected = [
            '.git', '__pycache__', 'node_modules',
            'venv', '.venv', 'dist', 'build'
        ]

        for dirname in expected:
            assert dirname in DATAMAP_EXCLUDE_DIRS, f"Missing exclude dir: {dirname}"


@pytest.mark.unit
class TestMaxDataSampleRows:
    """Tests for MAX_DATA_SAMPLE_ROWS constant."""

    def test_constant_value(self):
        """Test that the constant has an appropriate value."""
        assert MAX_DATA_SAMPLE_ROWS == 5
        assert isinstance(MAX_DATA_SAMPLE_ROWS, int)


@pytest.mark.unit
class TestTypeInferenceExtraRows:
    """Tests for TYPE_INFERENCE_EXTRA_ROWS constant."""

    def test_constant_value(self):
        """Test that the constant has an appropriate value."""
        assert TYPE_INFERENCE_EXTRA_ROWS == 100
        assert isinstance(MAX_DATA_SAMPLE_ROWS, int)


@pytest.mark.unit
class TestGetDataSourceSignature:
    """Tests for get_data_source_signature function."""

    def test_csv_signature(self):
        """Test that CSV file signature is extracted correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a CSV file
            csv_content = "name,age,city\nAlice,30,NYC\nBob,25,LA\nCharlie,35,Chicago"
            csv_file = Path(tmpdir) / "test.csv"
            csv_file.write_text(csv_content)

            signature = get_data_source_signature("test.csv", tmpdir)

            assert 'error' not in signature
            assert signature['path'] == 'test.csv'
            assert signature['extension'] == '.csv'
            assert signature['num_rows'] == 3
            assert signature['num_columns'] == 3
            assert 'name' in signature['column_names']
            assert 'age' in signature['column_names']
            assert 'city' in signature['column_names']

    def test_csv_column_types(self):
        """Test that column types are inferred correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_content = "id,value,name\n1,10.5,Alice\n2,20.3,Bob"
            csv_file = Path(tmpdir) / "test.csv"
            csv_file.write_text(csv_content)

            signature = get_data_source_signature("test.csv", tmpdir)

            assert 'column_types' in signature
            assert signature['column_types']['id'] == 'integer'
            assert signature['column_types']['value'] == 'float'
            assert signature['column_types']['name'] == 'string'

    def test_json_signature(self):
        """Test that JSON file signature is extracted correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a JSON file (array of objects)
            json_content = [
                {"name": "Alice", "age": 30},
                {"name": "Bob", "age": 25}
            ]
            json_file = Path(tmpdir) / "test.json"
            json_file.write_text(json.dumps(json_content))

            signature = get_data_source_signature("test.json", tmpdir)

            assert 'error' not in signature
            assert signature['path'] == 'test.json'
            assert signature['extension'] == '.json'
            assert signature['num_rows'] == 2
            assert 'name' in signature['column_names']
            assert 'age' in signature['column_names']

    def test_sample_data_included(self):
        """Test that sample data is included in signature."""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_content = "id,value\n1,100\n2,200\n3,300\n4,400\n5,500\n6,600"
            csv_file = Path(tmpdir) / "test.csv"
            csv_file.write_text(csv_content)

            signature = get_data_source_signature("test.csv", tmpdir)

            assert 'sample_data' in signature
            assert len(signature['sample_data']) <= MAX_DATA_SAMPLE_ROWS

    def test_numeric_stats_included(self):
        """Test that numeric statistics are included for numeric columns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_content = "id,value\n1,100\n2,200\n3,300"
            csv_file = Path(tmpdir) / "test.csv"
            csv_file.write_text(csv_content)

            signature = get_data_source_signature("test.csv", tmpdir)

            assert 'numeric_stats' in signature
            assert 'value' in signature['numeric_stats']
            assert signature['numeric_stats']['value']['min'] == 100
            assert signature['numeric_stats']['value']['max'] == 300
            assert signature['numeric_stats']['value']['mean'] == 200.0

    def test_null_counts_included(self):
        """Test that null counts are included in signature."""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_content = "id,value\n1,100\n2,\n3,300"
            csv_file = Path(tmpdir) / "test.csv"
            csv_file.write_text(csv_content)

            signature = get_data_source_signature("test.csv", tmpdir)

            assert 'null_counts' in signature
            # 'value' column has one null
            assert signature['null_counts']['value'] >= 1

    def test_file_not_found(self):
        """Test that missing file returns error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            signature = get_data_source_signature("nonexistent.csv", tmpdir)

            assert 'error' in signature
            assert 'not found' in signature['error'].lower()

    def test_file_size_included(self):
        """Test that file size is included in signature."""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_content = "id,value\n1,100"
            csv_file = Path(tmpdir) / "test.csv"
            csv_file.write_text(csv_content)

            signature = get_data_source_signature("test.csv", tmpdir)

            assert 'file_size' in signature
            assert signature['file_size'] > 0


@pytest.mark.unit
class TestCollectDataFiles:
    """Tests for collect_data_files function."""

    def test_collects_csv_files(self):
        """Test that CSV files are collected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a CSV file
            csv_file = Path(tmpdir) / "test.csv"
            csv_file.write_text("col1,col2\n1,2")

            files = collect_data_files(tmpdir)

            assert len(files) == 1
            assert files[0]['path'] == 'test.csv'

    def test_collects_multiple_data_types(self):
        """Test that multiple data file types are collected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create various data files
            (Path(tmpdir) / "data.csv").write_text("col1,col2\n1,2")
            (Path(tmpdir) / "data.json").write_text('[{"a": 1}]')

            files = collect_data_files(tmpdir)

            assert len(files) == 2
            paths = [f['path'] for f in files]
            assert 'data.csv' in paths
            assert 'data.json' in paths

    def test_excludes_venv_directory(self):
        """Test that venv directory is excluded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file in venv
            venv_dir = Path(tmpdir) / "venv" / "data"
            venv_dir.mkdir(parents=True)
            (venv_dir / "test.csv").write_text("col1,col2\n1,2")

            # Create a file outside venv
            (Path(tmpdir) / "data.csv").write_text("col1,col2\n1,2")

            files = collect_data_files(tmpdir)

            assert len(files) == 1
            assert files[0]['path'] == 'data.csv'

    def test_respects_max_files_limit(self):
        """Test that max_files limit is respected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create many files
            for i in range(20):
                (Path(tmpdir) / f"data{i}.csv").write_text(f"col{i}\n{i}")

            files = collect_data_files(tmpdir, max_files=5)

            assert len(files) == 5

    def test_handles_empty_directory(self):
        """Test handling of empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            files = collect_data_files(tmpdir)

            assert len(files) == 0

    def test_handles_nested_directories(self):
        """Test collection from nested directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create nested structure
            nested = Path(tmpdir) / "data" / "raw"
            nested.mkdir(parents=True)
            (nested / "input.csv").write_text("col1\n1")
            (Path(tmpdir) / "output.csv").write_text("col1\n1")

            files = collect_data_files(tmpdir)

            assert len(files) == 2
            paths = [f['path'] for f in files]
            assert 'output.csv' in paths
            # Use pathlib for cross-platform path handling
            expected_nested_path = str(Path('data') / 'raw' / 'input.csv')
            assert expected_nested_path in paths


@pytest.mark.unit
class TestGenerateDatamapPrompt:
    """Tests for generate_datamap_prompt function."""

    def test_generates_prompt_with_data_sources(self):
        """Test that prompt is generated with data source information."""
        data_sources = [
            {
                'path': 'data.csv',
                'extension': '.csv',
                'file_size': 1000,
                'num_rows': 100,
                'num_columns': 5,
                'column_names': ['id', 'name', 'value', 'date', 'active'],
                'column_types': {
                    'id': 'integer',
                    'name': 'string',
                    'value': 'float',
                    'date': 'string',
                    'active': 'boolean'
                },
                'null_counts': {'id': 0, 'name': 2, 'value': 5, 'date': 0, 'active': 0}
            }
        ]

        prompt = generate_datamap_prompt(data_sources)

        # Check that file info is included
        assert 'data.csv' in prompt
        assert '100' in prompt  # num_rows
        assert '5' in prompt or 'Columns' in prompt  # num_columns

    def test_includes_instruction_sections(self):
        """Test that prompt includes all required instruction sections."""
        data_sources = [
            {
                'path': 'test.csv',
                'extension': '.csv',
                'file_size': 100,
                'num_rows': 10,
                'num_columns': 2,
                'column_names': ['a', 'b'],
                'column_types': {'a': 'integer', 'b': 'string'},
                'null_counts': {'a': 0, 'b': 0}
            }
        ]

        prompt = generate_datamap_prompt(data_sources)

        # Check for key sections
        assert 'Data Overview' in prompt
        assert 'Data Schema' in prompt
        assert 'Data Quality' in prompt
        assert 'Relationships' in prompt
        assert 'Usage Recommendations' in prompt
        assert 'Code Integration' in prompt

    def test_handles_empty_data_sources(self):
        """Test handling of empty data sources list."""
        data_sources = []

        prompt = generate_datamap_prompt(data_sources)

        # Should still generate a valid prompt structure
        assert 'Data Overview' in prompt
        assert 'No data files found' in prompt

    def test_includes_tree_when_provided(self):
        """Test that tree output is included when provided."""
        data_sources = [
            {
                'path': 'data.csv',
                'extension': '.csv',
                'file_size': 100,
                'num_rows': 10,
                'num_columns': 2,
                'column_names': ['a', 'b'],
                'column_types': {'a': 'integer', 'b': 'string'},
                'null_counts': {'a': 0, 'b': 0}
            }
        ]
        tree_output = """project/
├── data/
│   └── data.csv
└── README.md"""

        prompt = generate_datamap_prompt(data_sources, tree_output=tree_output)

        # Check that tree is included
        assert 'Directory Tree' in prompt
        assert 'data/' in prompt
        assert 'data.csv' in prompt

    def test_no_tree_section_when_not_provided(self):
        """Test that tree section is not included when tree_output is None."""
        data_sources = [
            {
                'path': 'test.csv',
                'extension': '.csv',
                'file_size': 100,
                'num_rows': 10,
                'num_columns': 2,
                'column_names': ['a', 'b'],
                'column_types': {'a': 'integer', 'b': 'string'},
                'null_counts': {'a': 0, 'b': 0}
            }
        ]

        prompt = generate_datamap_prompt(data_sources, tree_output=None)

        # When tree_output is None, the "Directory Tree" section should not appear
        assert '## Directory Tree' not in prompt

    def test_includes_code_files_when_provided(self):
        """Test that code files are included for cross-reference."""
        data_sources = [
            {
                'path': 'data.csv',
                'extension': '.csv',
                'file_size': 100,
                'num_rows': 10,
                'num_columns': 2,
                'column_names': ['a', 'b'],
                'column_types': {'a': 'integer', 'b': 'string'},
                'null_counts': {'a': 0, 'b': 0}
            }
        ]
        code_files = [
            {'path': 'analyze.py', 'size': 500},
            {'path': 'process.py', 'size': 300}
        ]

        prompt = generate_datamap_prompt(data_sources, code_files=code_files)

        assert 'Related Code Files' in prompt
        assert 'analyze.py' in prompt
        assert 'process.py' in prompt


@pytest.mark.unit
class TestLoadDatamapToContext:
    """Tests for load_datamap_to_context async function."""

    @pytest.mark.asyncio
    async def test_returns_error_on_empty_result(self):
        """Test that empty result returns proper error dict."""
        class MockMCPClient:
            async def call_tool(self, server, tool, args):
                return None

        result = await load_datamap_to_context(MockMCPClient(), '/path/to/.datamap', '/path')

        assert result['status'] == 'error'
        assert 'empty result' in result['message'].lower()

    @pytest.mark.asyncio
    async def test_returns_parsed_json_on_success(self):
        """Test that valid JSON response is parsed correctly."""
        class MockMCPClient:
            async def call_tool(self, server, tool, args):
                return '{"status": "success", "message": "Loaded"}'

        result = await load_datamap_to_context(MockMCPClient(), '/path/to/.datamap', '/path')

        assert result['status'] == 'success'
        assert result['message'] == 'Loaded'

    @pytest.mark.asyncio
    async def test_handles_json_decode_error(self):
        """Test that invalid JSON returns proper error dict."""
        class MockMCPClient:
            async def call_tool(self, server, tool, args):
                return 'not valid json {'

        result = await load_datamap_to_context(MockMCPClient(), '/path/to/.datamap', '/path')

        assert result['status'] == 'error'
        assert 'Failed to parse' in result['message']

    @pytest.mark.asyncio
    async def test_handles_long_error_response_truncation(self):
        """Test that long error responses are truncated in error message."""
        class MockMCPClient:
            async def call_tool(self, server, tool, args):
                return 'x' * 200  # Long non-JSON string

        result = await load_datamap_to_context(MockMCPClient(), '/path/to/.datamap', '/path')

        assert result['status'] == 'error'
        # Should be truncated with ...
        assert '...' in result['message']
        # Should not contain full 200 chars
        assert 'x' * 200 not in result['message']

    @pytest.mark.asyncio
    async def test_passes_session_id_when_provided(self):
        """Test that session_id is passed to MCP client when provided."""
        captured_args = {}

        class MockMCPClient:
            async def call_tool(self, server, tool, args):
                captured_args.update(args)
                return '{"status": "success"}'

        await load_datamap_to_context(
            MockMCPClient(),
            '/path/to/.datamap',
            '/path',
            session_id='test-session-123'
        )

        assert captured_args.get('session_id') == 'test-session-123'

    @pytest.mark.asyncio
    async def test_omits_session_id_when_not_provided(self):
        """Test that session_id is not passed when None."""
        captured_args = {}

        class MockMCPClient:
            async def call_tool(self, server, tool, args):
                captured_args.update(args)
                return '{"status": "success"}'

        await load_datamap_to_context(MockMCPClient(), '/path/to/.datamap', '/path')

        assert 'session_id' not in captured_args


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
