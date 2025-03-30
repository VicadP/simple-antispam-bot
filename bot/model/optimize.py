from bot.config.settings import Settings
from bot.core.encoder import TextEncoder
from bot.data.dataset import DatasetManager
from bot.model.utils import save_study_results
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.naive_bayes import GaussianNB
import optuna
import numpy as np


def run_optimization():
    encoder = TextEncoder(Settings.MODEL_CLS)
    dm = DatasetManager()
    X, y = encoder.encode(dm.get_X()), dm.get_y() # энкодер pre-trained, поэтому можем считать эмбединги вне пайплайна без лика
    cv = StratifiedKFold(n_splits=10, shuffle=True, random_state=Settings.RNG_INT)

    def objective_nb(trial: optuna.Trial) -> float:
        var_smoothing = trial.suggest_float("var_smoothing", 1e-8, 1e1, log=True)
        model = GaussianNB(var_smoothing=var_smoothing)
        return cross_val_score(model, X, y, cv=cv, scoring="f1").mean()

    def objective_svc(trial: optuna.Trial) -> float:
        C = trial.suggest_float("C", 1.0, 1e2, log=True)
        loss = trial.suggest_categorical("loss", ["hinge", "squared_hinge"])
        model = LinearSVC(C=C, loss=loss, max_iter=10_000, random_state=Settings.RNG_INT)
        y_transformed = np.where(y == 0, -1, 1)
        return cross_val_score(model, X, y_transformed, cv=cv, scoring="f1").mean()

    def objective_logreg(trial: optuna.Trial) -> float:
        C = trial.suggest_float("C", 1.0, 1e2, log=True)
        penalty = trial.suggest_categorical("penalty", ["l1", "l2"])
        model = LogisticRegression(C=C, penalty=penalty, solver="liblinear", max_iter=10_000, random_state=Settings.RNG_INT)
        return cross_val_score(model, X, y, cv=cv, scoring="f1").mean()
    
    study_nb = optuna.create_study(direction="maximize", 
                                   sampler=optuna.samplers.TPESampler(), 
                                   study_name=f"gaussian_nb")
    study_nb.optimize(objective_nb, n_trials=100, n_jobs=-1)
    save_study_results(study_nb, f"gaussian_nb")

    study_svc = optuna.create_study(direction="maximize", 
                                    sampler=optuna.samplers.TPESampler(), 
                                    study_name=f"linear_svc")
    study_svc.optimize(objective_svc, n_trials=100, n_jobs=-1)
    save_study_results(study_svc, f"linear_svc")

    study_logreg = optuna.create_study(direction="maximize", 
                                       sampler=optuna.samplers.TPESampler(), 
                                       study_name=f"logreg")
    study_logreg.optimize(objective_logreg, n_trials=100, n_jobs=-1)
    save_study_results(study_logreg, f"logreg")

if __name__ == "__main__":
    run_optimization()