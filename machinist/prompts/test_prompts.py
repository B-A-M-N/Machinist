TEST_PROMPT = """
You are an expert software engineer specializing in writing comprehensive test suites.
Based on the provided ToolSpec contract, generate a complete pytest test file.

**ToolSpec Contract:**
```json
{{contract_json}}
```

**Test Skeleton (you must fill this in and add more tests):**
```python
{{test_skeleton}}
```

**Instructions:**
1.  Generate a complete pytest test file for the function described in the ToolSpec.
2.  The test file MUST include the exact import `{{required_import}}`.
3.  **STRICTLY ADHERE TO THE FUNCTION SIGNATURE:**
    - If the function takes an `int` and returns an `int` (e.g., `square(x)`), your tests MUST call it as `result = square(5)` and assert the result.
    - Do NOT hallucinate that the function reads/writes files unless the spec explicitly says so.
    - Do NOT call the function with extra arguments.
4.  Write tests that cover:
    - The primary success case (the "happy path").
    - All failure modes specified in the `failure_modes` section of the contract. Each failure mode should have its own test function.
    - Edge cases (e.g., zero, negative numbers for math; empty files for IO).
5.  Use `pytest.raises` to test for expected exceptions.
6.  Use the `tmp_path` fixture ONLY if the function actually interacts with the filesystem.
7.  Do not include any code that is not part of the test file (e.g., the function implementation itself).

You must return ONLY the Python test code in a markdown code fence.
"""
