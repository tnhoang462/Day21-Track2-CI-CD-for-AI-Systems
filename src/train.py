import mlflow
import mlflow.sklearn
import pandas as pd
import yaml
import json
import joblib
import os
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    confusion_matrix,
    precision_recall_fscore_support,
)

EVAL_THRESHOLD = 0.70

_MODEL_REGISTRY = {
    "random_forest": RandomForestClassifier,
    "gradient_boosting": GradientBoostingClassifier,
    "logistic_regression": LogisticRegression,
}


def _build_model(model_type: str, params: dict):
    if model_type not in _MODEL_REGISTRY:
        raise ValueError(
            f"Unknown model_type='{model_type}'. "
            f"Available: {list(_MODEL_REGISTRY)}"
        )
    cls = _MODEL_REGISTRY[model_type]
    if model_type == "logistic_regression":
        return cls(**params, random_state=42, max_iter=1000)
    return cls(**params, random_state=42)


def _check_label_drift(y_train: pd.Series, threshold: float = 0.10) -> dict:
    """Bonus 5: canh bao neu phan phoi nhan bi lech."""
    dist = y_train.value_counts(normalize=True).sort_index().to_dict()
    dist = {int(k): float(v) for k, v in dist.items()}
    for label, ratio in dist.items():
        if ratio < threshold:
            print(
                f"WARNING: Lop {label} chiem {ratio*100:.1f}% mau "
                f"(nguong canh bao: {threshold*100:.0f}%)"
            )
    return dist


def _write_report(y_true, y_pred, classes=(0, 1, 2)) -> str:
    """Bonus 3: ghi confusion matrix + precision/recall vao outputs/report.txt."""
    cm = confusion_matrix(y_true, y_pred, labels=list(classes))
    p, r, f, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=list(classes), zero_division=0
    )
    lines = ["Confusion Matrix (rows=true, cols=pred):"]
    header = "      " + " ".join(f"pred_{c:<3d}" for c in classes)
    lines.append(header)
    for i, row in enumerate(cm):
        lines.append(f"true_{classes[i]} " + " ".join(f"{v:7d}" for v in row))
    lines.append("")
    lines.append("Per-class metrics:")
    lines.append(f"{'class':<7s} {'precision':>10s} {'recall':>10s} {'f1':>10s}")
    for i, c in enumerate(classes):
        lines.append(
            f"{c:<7d} {p[i]:>10.4f} {r[i]:>10.4f} {f[i]:>10.4f}"
        )
    text = "\n".join(lines)
    os.makedirs("outputs", exist_ok=True)
    with open("outputs/report.txt", "w") as f:
        f.write(text + "\n")
    return text


def train(
    params: dict,
    data_path: str = "data/train_phase1.csv",
    eval_path: str = "data/eval.csv",
) -> float:
    """
    Huan luyen mo hinh va ghi nhan ket qua vao MLflow.

    Tham so:
        params     : dict chua model_type + sieu tham so cho thuat toan duoc chon.
                     Vi du: {"model_type": "random_forest", "n_estimators": 200, ...}
        data_path  : duong dan den file du lieu huan luyen.
        eval_path  : duong dan den file du lieu danh gia.

    Tra ve:
        accuracy (float): do chinh xac tren tap danh gia.
    """
    df_train = pd.read_csv(data_path)
    df_eval = pd.read_csv(eval_path)

    X_train = df_train.drop(columns=["target"])
    y_train = df_train["target"]
    X_eval = df_eval.drop(columns=["target"])
    y_eval = df_eval["target"]

    label_dist = _check_label_drift(y_train)

    model_params = {k: v for k, v in params.items() if k != "model_type"}
    model_type = params.get("model_type", "random_forest")

    with mlflow.start_run():
        mlflow.log_params(params)

        model = _build_model(model_type, model_params)
        model.fit(X_train, y_train)

        preds = model.predict(X_eval)
        acc = accuracy_score(y_eval, preds)
        f1 = f1_score(y_eval, preds, average="weighted")

        mlflow.log_metric("accuracy", acc)
        mlflow.log_metric("f1_score", f1)
        mlflow.sklearn.log_model(model, "model")

        report = _write_report(y_eval, preds)
        mlflow.log_artifact("outputs/report.txt")

        print(f"Model: {model_type} | Accuracy: {acc:.4f} | F1: {f1:.4f}")
        print(report)

        os.makedirs("outputs", exist_ok=True)
        with open("outputs/metrics.json", "w") as f:
            json.dump(
                {
                    "accuracy": acc,
                    "f1_score": f1,
                    "model_type": model_type,
                    "label_distribution": label_dist,
                },
                f,
            )

        os.makedirs("models", exist_ok=True)
        joblib.dump(model, "models/model.pkl")

    return acc


if __name__ == "__main__":
    with open("params.yaml") as f:
        params = yaml.safe_load(f)
    train(params)
