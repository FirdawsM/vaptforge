"""Loads test_definitions.yaml into a list of test dicts."""

import yaml


def load_definitions(path: str) -> list[dict]:
    with open(path) as f:
        data = yaml.safe_load(f)
    return data["tests"]
