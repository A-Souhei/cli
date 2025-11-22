#!/bin/bash
# Run the previously failing tests

set -e

echo "Running previously failing tests..."
echo "=================================="

./venv/bin/python -m pytest -xvs \
  tests/test_coder_mcp.py::TestCoderMCP::test_roll_the_dice_without_session \
  tests/test_coder_mcp.py::TestCoderMCP::test_spin_the_roulette_missing_text \
  tests/test_text_to_sequence.py::TestTextToSequenceEndpoint::test_text_to_sequence_empty_text \
  tests/test_text_to_sequence.py::TestTextToSequenceEndpoint::test_text_to_sequence_missing_text

echo "=================================="
echo "All tests completed!"
