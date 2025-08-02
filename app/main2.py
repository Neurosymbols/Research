import pandas as pd
import re
import json
import unicodedata


from scipy.stats import truncnorm, norm
import numpy as np


path = "./data/ontologies"
input_path = "./data/input"
output_path = "./data/output"
specs_file = "epoch_2_specs.csv"
output_specs_file = "epoch_2_specs.json"

def clean_param_name(raw):
    # 1. Remove text in parentheses (units)
    raw = re.sub(r"\(.*?\)", "", raw)

    # 2. Normalize Unicode characters to ASCII equivalents
    raw = unicodedata.normalize('NFKD', raw).encode('ascii', 'ignore').decode()

    # 3. Remove any remaining non-alphanumeric characters (except space and hyphen)
    raw = re.sub(r"[^\w\s-]", "", raw)

    # 4. Collapse multiple spaces and trim
    return re.sub(r"\s+", " ", raw).strip()

def extract_number(value):
    if pd.isna(value):
        return None
    value = str(value).replace("–", "-").replace("−", "-").replace(" ", "").replace(",", "")
    match = re.search(r"[-+]?\d*\.?\d+", value)
    return float(match.group()) if match else None

def add_specs():
    df = pd.read_csv(f"{input_path}/{specs_file}")
    result = {}
    for _, row in df.iterrows():
        raw_param = row["Parameter (Xi)"]
        param_name = clean_param_name(raw_param)
        result[param_name] = {
            "NV": extract_number(row["Assumed process mean μ"]),
            "UL": extract_number(row["Upper spec limit (USL)"]),
            "LL": extract_number(row["Lower spec limit (LSL)"]),
            "tolerance": extract_number(row["3 σ distance†"])
        }
    with open(f"{output_path}/{output_specs_file}", "w") as f:
        json.dump(result, f, indent=2)

def generate_synthetic_data(
        N:int, 
        good_ratio:float, 
        bad_ratio:float,
        shift_std:int
    ):
    with open(f"{output_path}/{output_specs_file}", "r") as f:
        specs_data = json.load(f)
    def truncated_normal(mu, sigma, low, high, size):
        #calculate a and b to truncate the normal distribution between LSL and USL. This ensures the samples stay within spec limits → good panels.
        a, b = (low - mu) / sigma, (high - mu) / sigma
        return truncnorm(a, b, loc=mu, scale=sigma).rvs(size) #represents normal distribution N(μ, σ)
    def shifted_normal(mu, sigma, shift_std, size):
        return norm.rvs(loc=mu + shift_std * sigma, scale=sigma, size=size)
    
    good_samples = {}
    bad_samples = {}
    for param, vals in specs_data.items():
        mu = vals["NV"]
        sigma = vals["tolerance"] / 3  # Assuming 3σ range
        LSL = vals["LL"] if vals["LL"] is not None else mu - (3 * sigma)
        USL = vals["UL"] if vals["UL"] is not None else mu + (3 * sigma)

        good_samples[param] = truncated_normal(mu, sigma, LSL, USL, int(N * good_ratio))
        bad_samples[param] = shifted_normal(mu, sigma, shift_std, int(N * bad_ratio))
    
    # Create DataFrames
    df_good = pd.DataFrame(good_samples)
    df_good["label"] = 0

    df_bad = pd.DataFrame(bad_samples)
    df_bad["label"] = 1

    # Combine and shuffle
    df_all = pd.concat([df_good, df_bad]).sample(frac=1).reset_index(drop=True)

    # Move 'label' column to the front
    cols = ['label'] + [col for col in df_all.columns if col != 'label']
    df_all = df_all[cols]
    df_all.to_csv(f"{input_path}/synthetic_data_factory_epoch2.csv", index=False)

# add_specs()
generate_synthetic_data(
    N=1000,
    good_ratio=0.7,
    bad_ratio=0.3,
    shift_std=2
)