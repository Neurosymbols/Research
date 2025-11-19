import random
import numpy as np
import pandas as pd
import scipy.stats as st
import json


output_path = "./app/data/output/epoch3-7"
input_path = "./app/data/input/epoch3-7"

process_parameters = {
    # monte carlo simluation, #discrete event simulation
    "Stencil thickness": {
        "NV": 0.100,
        "tolerance": 0.005,
        "USL": 0.105,
        "LSL": 0.095,
        "sigma_frac": [2,2.5,3,3.5,4]
    #  σ = tol/x → 0.005 / 3 = 0.00167 (1.67% of NV) ✅ realistic (tight dimensional control)
    }
}

def generate_samples_ppf(param_info, n=5000):
    NV = param_info["NV"]
    sigma_fracs = np.array(param_info["sigma_frac"])
    tolerance = param_info["tolerance"]
    scales = tolerance / sigma_fracs #["tol/2", "tol/2.5", "tol/3"]
    # Generate matrix of U(0,1) — shape: (n, num_sigma_fracs)
    #[
    #       2 2.5 3 3.5 4
    #   1   RAND() rand() RAND() rand()
    #   2
    #   3
    #   4
    #   5    
    #]
    r = np.random.rand(n, len(sigma_fracs))
    # Vectorized PPF over the entire matrix
    return st.norm.ppf(r, loc=NV, scale=scales)

df_iterations = pd.DataFrame(columns=[f"stencil_thickness_{i}" for i in process_parameters['Stencil thickness']['sigma_frac']]) 
for i in range(0, 100):
    arr = generate_samples_ppf(
        process_parameters['Stencil thickness'],
        n = 5000
    )
    df = pd.DataFrame(arr, columns=[f"stencil_thickness_{i}" for i in process_parameters['Stencil thickness']['sigma_frac']])
    # Compute ratio for each column
    ratio = df.apply(
        lambda col: (
            round(((col > process_parameters['Stencil thickness']['USL']).sum() / len(df))*100,2)
            # (col > process_parameters['Stencil thickness']['USL']).sum() / len(df)
        )
    )
    # Append ratio row to DataFrame
    df.loc["ratio"] = ratio

    df.to_csv(f"{output_path}/stencil_thickness_test.csv")

    df_iterations.loc[f"iteration_{i+1}"] = ratio

    i += 1
    print(f"iteration {i}")
    # if(i == 1):
    #     break
mean_row = df_iterations.mean(axis=0)
df_iterations.loc["mean_across_rows"] = round(mean_row, 3)
df_iterations.to_csv(f"{output_path}/stencil_thickness_test_iterations_2.csv")