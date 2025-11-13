import random
import pandas as pd
import scipy.stats as st
import json


output_path = "./app/data/output/epoch3-7"

process_parameters = {
    "Aperture area ratio": {
        "NV": 0.66,
        "tolerance": None,
        "USL": None,
        "LSL": 0.66,  # since only minimum is specified
        "target_defect_rate": [0.005, 0.009], #fine tune range here
        "sigma_pct": 0.03
    }
}

# Function to generate a single sample using PPF
def generate_value_ppf(param_info):
    return st.norm.ppf(random.random(), loc=param_info['mu'], scale=param_info['sigma'])

# Function to generate multiple samples
def generate_samples_ppf(param_info, n=1000):
    return [generate_value_ppf(param_info) for _ in range(n)]

with open(f"{output_path}/inpect_aar.json","w") as f:
    param_info = process_parameters['Aperture area ratio']
    # Pick random target defect rate from given range for the parameter
    p_target = random.uniform(param_info['target_defect_rate'][0], param_info['target_defect_rate'][1])
    print("p_target", p_target)
    sigma = param_info['sigma_pct'] * param_info['NV']
    print("sigma", sigma)
    # Find mean μ such that P(X < LSL) = p_target
    z_p = st.norm.ppf(p_target)     # z-score for that percentile (negative)
    print("z-score", z_p)
    mu = param_info['LSL'] - z_p * sigma          # shift mean upward so only p_target < LSL
    print("mu", mu)
    param_info['mu'] = mu
    param_info['sigma'] = sigma
    data = generate_samples_ppf(param_info)
    
    json.dump({"aar":data[0:100], "out_of_spec": len([v for v in data if v<0.66])}, f, indent = 2)
