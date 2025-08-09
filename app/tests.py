import pandas as pd
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
    pred
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
    print(metrics)
    return metrics

def root_cause_identification(
    expected,
    generated
):
    expected_df_rule = expected.filter(regex=r'^FC')
    generated_df_rule = generated.filter(regex=r'^FC')
    evaluation_matrix_per_rule = {}
    for i, col in enumerate(expected_df_rule.columns):
        evaluation_matrix_per_rule[col] = compute_evaluation_matrix(
            expected_df_rule[col],
            generated_df_rule[col]
        )
    evaluation_matrix_per_rule = [{"rule":k, **v} for k,v in evaluation_matrix_per_rule.items()]

    df = pd.DataFrame(evaluation_matrix_per_rule)
    numeric_cols = df.columns[5:]
    mean_row = df[numeric_cols].mean()
    mean_row[df.columns[0]] = 'Mean'
    df.loc[len(df)] = mean_row
    return df