# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional


def output_json_result(result: Dict[str, Any], output_path: Optional[str]) -> None:
    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)

    if not output_path:
        return

    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as file:
        file.write(text)
        file.write("\n")

