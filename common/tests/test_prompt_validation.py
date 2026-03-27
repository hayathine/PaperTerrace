import re

import pytest

from common import dspy_seed_prompt


def test_all_prompts_are_valid_strings():
    # Get all variables in dspy_seed_prompt.py that end with _SEED or _PROMPT
    prompt_names = [
        name
        for name in dir(dspy_seed_prompt)
        if name.endswith("_SEED") or name.endswith("_PROMPT")
    ]
    for name in prompt_names:
        val = getattr(dspy_seed_prompt, name)
        assert isinstance(val, str), f"{name} should be a string"
        assert len(val) > 0, f"{name} should not be empty"


def test_prompt_placeholders_syntax():
    # Check that all prompts have balanced braces
    prompt_names = [
        name
        for name in dir(dspy_seed_prompt)
        if name.endswith("_SEED") or name.endswith("_PROMPT")
    ]
    for name in prompt_names:
        val = getattr(dspy_seed_prompt, name)
        # Check if they have balanced braces
        open_braces = val.count("{")
        close_braces = val.count("}")
        assert open_braces == close_braces, f"Unbalanced braces in {name}"

        # In actual prompts, doubled braces are used for escaping in JSON chunks.
        # e.g. {{ "key": "{value}" }}
        # We should check if they can be formatted without error if we provide dummy keys.

        # Extract all keys inside single braces
        keys = re.findall(r"(?<!\{)\{([a-zA-Z0-9_]+)\}(?!\})", val)

        # If there are keys, they should be well-formed.
        for key in keys:
            assert key.isidentifier(), f"Invalid placeholder key '{key}' in {name}"


@pytest.mark.parametrize(
    "prompt_name, expected_keys",
    [
        ("DICT_TRANSLATE_LLM_PROMPT", ["paper_title", "target_word", "lang_name"]),
        ("PAPER_SUMMARY_FROM_PDF_PROMPT", ["lang_name", "keyword_focus"]),
        (
            "CHAT_GENERAL_FROM_PDF_PROMPT",
            ["lang_name", "history_text", "user_message"],
        ),
        ("ADVERSARIAL_CRITIQUE_FROM_PDF_PROMPT", ["lang_name"]),
    ],
)
def test_specific_prompt_keys(prompt_name, expected_keys):
    prompt_text = getattr(dspy_seed_prompt, prompt_name)
    for key in expected_keys:
        placeholder = "{" + key + "}"
        assert placeholder in prompt_text, f"Missing {placeholder} in {prompt_name}"
