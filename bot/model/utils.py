from bot.config.settings import Settings
import json
import time
from optuna import Study
from typing import Union
from pathlib import Path

def save_study_results(study: Study, model_name: str):
    path = Settings.ROOT_PATH / "bot/model/optunalogs" / f"{model_name}_{int(time.time())}.json"
    results = {
        'best_score': study.best_value,
        'best_params': study.best_params
    }
    with path.open(mode="w", encoding="utf-8") as f:
        json.dump(results, f, indent=4)

def read_best_params(file_path: Union[str, Path]) -> dict:
    with open(file_path) as f:
        data = json.load(f)
    return data['best_params']