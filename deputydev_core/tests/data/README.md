# Test Data Directory

This directory contains test data files used by the test suite.

## Structure

- `sample_code/` - Sample source code files for testing
- `fixtures/` - JSON and YAML fixture files
- `mock_responses/` - Mock API response files
- `test_files/` - Various file types for testing file operations

## Usage

Test data files should be loaded using the `test_data_dir` fixture from conftest.py:

```python
def test_something(test_data_dir):
    data_file = test_data_dir / "fixtures" / "sample_data.json"
    # Use the data file in your test
```