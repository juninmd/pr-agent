
import time
import pytest
from pr_agent.algo.git_patch_processing import decouple_and_convert_to_hunks_with_lines_numbers, extract_hunk_lines_from_patch
from pr_agent.algo.diff_processing import add_ai_summary_top_patch
from pr_agent.algo.types import EDIT_TYPE

class MockFile:
    def __init__(self, filename="test_file.py"):
        self.filename = filename
        self.edit_type = EDIT_TYPE.MODIFIED
        self.ai_file_summary = {'long_summary': "This is a summary."}

def test_decouple_and_convert_performance():
    # Generate a large patch with many hunks
    num_hunks = 1000
    lines_per_hunk = 10
    patch_lines = []

    for i in range(num_hunks):
        patch_lines.append(f"@@ -{i*20},{lines_per_hunk} +{i*20},{lines_per_hunk} @@ hunk header {i}")
        for j in range(lines_per_hunk):
            patch_lines.append(f" context line {j}")
            patch_lines.append(f"+added line {j}")
            patch_lines.append(f"-deleted line {j}")

    patch = "\n".join(patch_lines)
    file = MockFile("test_file.py")

    start_time = time.time()
    result = decouple_and_convert_to_hunks_with_lines_numbers(patch, file)
    end_time = time.time()

    duration = end_time - start_time
    print(f"Processed {len(patch_lines)} lines in {duration:.4f}s")

    # Performance assertion: 30000 lines should be very fast with list optimization.
    assert duration < 2.0, f"Processing took too long: {duration}s"
    assert "test_file.py" in result
    assert "hunk header" in result

def test_extract_hunk_lines_performance():
    num_hunks = 1000
    lines_per_hunk = 10
    patch_lines = []

    for i in range(num_hunks):
        patch_lines.append(f"@@ -{i*20},{lines_per_hunk} +{i*20},{lines_per_hunk} @@ hunk header {i}")
        for j in range(lines_per_hunk):
            patch_lines.append(f" context line {j}")

    patch = "\n".join(patch_lines)

    start_time = time.time()
    patch_text, selected_lines = extract_hunk_lines_from_patch(patch, "file.txt", 0, 100000, "right")
    end_time = time.time()

    duration = end_time - start_time
    print(f"Extracted hunks in {duration:.4f}s")
    assert duration < 2.0
    assert "file.txt" in patch_text

def test_add_ai_summary_top_patch_correctness():
    file = MockFile()

    # Case 1: Header at start
    patch = "\n\n## File: 'test.py'\n\n@@ -1,1 +1,1 @@\n"
    # Expected: Original logic inserts summary after the header line.
    expected = "\n\n## File: 'test.py'\n### AI-generated changes summary:\nThis is a summary.\n\n@@ -1,1 +1,1 @@\n"
    result = add_ai_summary_top_patch(file, patch)
    assert result == expected

    # Case 2: Header lower case
    patch = "\n\n## file: 'test.py'\n\n@@ ..."
    expected = "\n\n## file: 'test.py'\n### AI-generated changes summary:\nThis is a summary.\n\n@@ ..."
    result = add_ai_summary_top_patch(file, patch)
    assert result == expected

    # Case 3: No header
    patch = "@@ -1,1 +1,1 @@\n"
    result = add_ai_summary_top_patch(file, patch)
    assert result == patch

def test_add_ai_summary_performance():
    # Create a large patch
    file = MockFile()
    lines = ["line" + str(i) for i in range(10000)]
    patch = "\n\n## File: 'large.py'\n\n" + "\n".join(lines)

    start_time = time.time()
    add_ai_summary_top_patch(file, patch)
    end_time = time.time()
    duration = end_time - start_time
    print(f"add_ai_summary_top_patch took {duration:.4f}s")

    assert duration < 0.1, f"Adding AI summary took too long: {duration}s"
