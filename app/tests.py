import pandas as pd
import json
from sklearn.metrics import confusion_matrix, accuracy_score, precision_score, recall_score, f1_score, matthews_corrcoef


def test_generated_output(
    expected,
    generated     
):
    interaction_match = (generated["interaction"] == expected["interaction"])
    defect_match = (generated["defect"] == expected["defect"])
    total_rows = len(expected)

    # Calculate match percentages
    interaction_match_pct = interaction_match.sum() / total_rows * 100
    defect_match_pct = defect_match.sum() / total_rows * 100

    match_summary = {
    "interaction_match_pct": float(round(interaction_match_pct, 2)),
    "defect_match_pct": float(round(defect_match_pct, 2))
    }
    print(match_summary)

def compute_evaluation_matrix(
    true,
    pred,
    output
):
    # Confusion matrix
    tn, fp, fn, tp = confusion_matrix(true, pred).ravel()
    metrics = {
        "TP": int(tp),
        "TN": int(tn),
        "FP": int(fp),
        "FN": int(fn),
        "Accuracy": round(accuracy_score(true, pred), 4),
        "Precision": round(precision_score(true, pred, zero_division=0), 4),
        "Recall": round(recall_score(true, pred, zero_division=0), 4),
        "F1 Score": round(f1_score(true, pred, zero_division=0), 4),
        "MCC": round(matthews_corrcoef(true, pred), 4),
        "FPR": float(fp / (fp + tn) if (fp + tn) > 0 else 0)
    }
    # Pass/fail check
    pass_fail = {
        "Precision": metrics['Precision'] >= 0.80,
        "Recall": metrics['Recall'] >= 0.85,
        "F1 Score": metrics['F1 Score'] >= 0.82,
        "FPR": metrics['FPR'] <= 0.05
    }
    with open(f"{output}.json", "w") as f:
        json.dump(metrics, f, indent=2)
    return metrics