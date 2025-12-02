import json
from typing import Any

import pandas as pd
from easydict import EasyDict


def save_json(data: EasyDict | dict, file_path: str) -> None:
    with open(file_path, "w") as f:
        json.dump(data, f)


def save_csv(data: pd.DataFrame, file_path: str) -> None:
    data.to_csv(file_path, index=False)


def save_txt(data: str, file_path: str) -> None:
    with open(file_path, "w") as f:
        f.write(data)


def save_md(data: str, file_path: str) -> None:
    with open(file_path, "w") as f:
        f.write(data)


def save_file(data: Any, file_path: str, mode: str = "w") -> None:
    if file_path.endswith(".json"):
        save_json(data, file_path)
    elif file_path.endswith(".csv"):
        save_csv(data, file_path)
    elif file_path.endswith(".txt"):
        save_txt(data, file_path)
    elif file_path.endswith(".md"):
        save_md(data, file_path)
    else:
        raise ValueError(f"Unsupported file type: {file_path}")


def load_json(file_path: str) -> EasyDict | dict:
    with open(file_path) as f:
        return json.load(f)


def load_csv(file_path: str) -> pd.DataFrame:
    return pd.read_csv(file_path)


def load_txt(file_path: str) -> str:
    with open(file_path) as f:
        return f.read()


def load_md(file_path: str) -> str:
    with open(file_path) as f:
        return f.read()


def load_file(file_path: str) -> Any:
    if file_path.endswith(".json"):
        return load_json(file_path)
    elif file_path.endswith(".csv"):
        return load_csv(file_path)
    elif file_path.endswith(".txt"):
        return load_txt(file_path)
    elif file_path.endswith(".md"):
        return load_md(file_path)
    else:
        raise ValueError(f"Unsupported file type: {file_path}")
