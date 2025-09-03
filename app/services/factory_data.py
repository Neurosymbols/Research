import json
import numpy as np
import pandas as pd
from scipy.stats import norm

def assign_seeds_to_qualities(path):
    with open(path, "r") as f:
        data = json.load(f)
        # Set seed for reproducibility: ensures the same random numbers are generated each run
        initial_seed = 30
        for k, v in data.items():
            v['seed'] = initial_seed
            initial_seed += 1
    with open(path, "w") as f:
        json.dump(data,f, indent=2)

def generate_values(values, input_path, output_path):
    with open(input_path) as f:
        data = json.load(f)
        synthetic_data_object = {}
        for k, v in data.items():
            assert "seed" in v, f"seed number not present for {k}"
            assert "NV" in v, f"mean value not present for {k}"
            assert "tolerance" in v, f"tolerance not present for {k}"
            assigned_seed, mean_value, tolernce = v.get("seed"), v.get("NV"), v.get("tolerance")
            np.random.seed(assigned_seed)
            value_array = np.random.rand(values)
            # Vectorized computation of inverse normal for all C8 values
            results = norm.ppf(value_array, loc=mean_value, scale=tolernce / 3)
            synthetic_data_object[k.lower()] = results
        # Convert to DataFrame
        df = pd.DataFrame(synthetic_data_object)
        # Save to CSV
        df.to_csv(output_path, index=False)
