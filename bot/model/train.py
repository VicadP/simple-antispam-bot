import warnings
warnings.filterwarnings(action='ignore')

import joblib
import logging
from bot.config.settings import Settings
from bot.core.encoder import TextEncoder
from bot.data.dataset import DatasetManager
from bot.model.utils import read_best_params
from sklearn.model_selection import StratifiedKFold
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("classifier_logger")

def run_train():
    try:
        encoder = TextEncoder(Settings.MODEL_CLS)
        dm = DatasetManager()
        X, y = encoder.encode(dm.get_X()), dm.get_y()
        cv = StratifiedKFold(n_splits=10, shuffle=True, random_state=Settings.RNG_INT)
        best_params = read_best_params(Settings.ROOT_PATH / "bot/model/optunalogs/linear_svc_1742725246.json")
        clf = CalibratedClassifierCV(
                LinearSVC(**best_params, max_iter=10_000, random_state=Settings.RNG_INT),
                method="sigmoid",
                ensemble=True,
                cv=cv
        )
        clf.fit(X, y)
        joblib.dump(clf, Settings.ROOT_PATH / "bot/core/classifier.joblib")
        logger.info("Модель успешно обучена и сохранена")
    except Exception as e:
        logger.error(f"Ошибка при обучении и сохранении модели: {e}")

if __name__ == "__main__":
    run_train()