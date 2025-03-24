from bot.config.settings import Queries
from bot.data.database import DatabaseManager
import pickle
import numpy as np
from numpy import ndarray
import csv

def get_embeddings() -> ndarray:
    db = DatabaseManager()
    embeddings = [pickle.loads(embedding[0]) for embedding in db.select_all(Queries.SELECT)]
    return np.array(embeddings)

def write_to_csv(csv_path, message: str, label: int = 1):
    with csv_path.open(mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";", quoting=csv.QUOTE_NONE, escapechar="\\")
        writer.writerow([message, label])
