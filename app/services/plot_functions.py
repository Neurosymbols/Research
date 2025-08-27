import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import seaborn as sns

from matplotlib.ticker import MultipleLocator
from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay

def plot_key(key_name:str, plot_file_path:str, output_path:str):
    df = pd.read_csv(plot_file_path)
    rb_scores = df['rbi_score'].value_counts().reset_index()
    rb_scores.columns = ["Score", "No of PCBs"]
    rb_scores = rb_scores.sort_values(by="Score", ascending=False)
    rb_scores.to_csv(f"{output_path}/rbi_score_freq_dist.csv", index=False)

    # Assuming df is your DataFrame and 'rbi_score' is the column
    scores = df[key_name].dropna()  # Remove NaN if any

    scores_pos = scores[scores > 0]

    fig, ax = plt.subplots(figsize=(8,5))

    # Histogram
    sns.histplot(
        scores_pos,
        bins=30,
        stat='count',
        edgecolor='black',
        alpha=0.6,
        ax=ax,
        color='skyblue'
    )
    # Labels & ticks
    ax.set_title("RBI Score Histogram + KDE (zeros excluded)")
    ax.set_xlabel("RBI Score")
    ax.set_ylabel("Frequency")
    ax.xaxis.set_major_locator(MultipleLocator(2))
    ax.yaxis.set_major_locator(MultipleLocator(100))

    plt.tight_layout()
    plt.show()