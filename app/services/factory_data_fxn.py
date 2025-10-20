from scipy.stats import truncnorm, norm, gaussian_kde, halfnorm

def generate_synthetic_data(
        N:int, 
        good_ratio:float, 
        bad_ratio:float,
        shift_std:int,
        generate_data=True,
        rule_interaction=False,
        version:int = 1,
        label:str="train"
    ):

    def truncated_normal(mu, sigma, low, high, size):
        #calculate a and b to truncate the normal distribution between LSL and USL. This ensures the samples stay within spec limits → good panels.
        a, b = (low - mu)/sigma, (high - mu)/sigma
        return truncnorm(a, b, loc=mu, scale=sigma).rvs(size) #represents normal distribution N(μ, σ)
    def shifted_normal(mu, sigma, shift_std, size):
        return norm.rvs(loc=mu + shift_std * sigma, scale=sigma, size=size)
    ################
    #TODO: audit the defect generation formulas for one sided specs
    ################
    def half_normal(bound, sigma, size, bound_type, good=True):
        if bound_type == "upper":
            if good:
                #sigma=0.2
                return bound - halfnorm.rvs(scale=sigma, size=size)
            else:
                return bound + halfnorm.rvs(scale=sigma, size=size)
        elif bound_type == "lower":
            if good:
                return bound + halfnorm.rvs(scale=sigma, size=size)
            else:
                return bound - halfnorm.rvs(scale=sigma, size=size)
    df_all = None
    #include non-null specs inside specs_data
    specs_data = {k:v for k,v in specs.items() if k in non_null_specs}
    if generate_data:
        good_samples = {}
        bad_samples = {}
        for param, vals in specs_data.items():
            if vals['NV'] is not None and vals['tolerance']:
                mu = vals["NV"]
                sigma = vals["tolerance"] / 3  # Assuming 3σ range
                LSL = vals["LL"] if vals["LL"] is not None else mu - (3 * sigma)
                USL = vals["UL"] if vals["UL"] is not None else mu + (3 * sigma)

                good_samples[param] = truncated_normal(mu, sigma, LSL, USL, int(N * good_ratio))
                bad_samples[param] = shifted_normal(mu, sigma, shift_std, int(N * bad_ratio))
            elif not vals['NV'] and not vals['tolerance']:
                if vals['UL']:
                    good_samples[param] = half_normal(vals['UL'], 0.2, int(N * good_ratio), 'upper', True)
                    bad_samples[param] = half_normal(vals['UL'], 0.2, int(N * bad_ratio), 'upper', False)
                elif vals['LL']:
                    good_samples[param] = half_normal(vals['LL'], 0.2, int(N * good_ratio), 'lower', True)
                    bad_samples[param] = half_normal(vals['LL'], 0.2, int(N * bad_ratio), 'lower', False)
            elif vals['NV'] is not None and vals['tolerance'] == 0.0:
                # Case: zero tolerance → deterministic samples
                good_samples[param] = [mu] * int(N * good_ratio)
                bad_samples[param] = [mu] * int(N * bad_ratio)

        # Create DataFrames
        df_good_panels = pd.DataFrame(good_samples)
        df_bad_panels = pd.DataFrame(bad_samples)
        # Combine and shuffle
        df_all = pd.concat([df_good_panels, df_bad_panels]).sample(frac=1).reset_index(drop=True)

        #output dataframes to csv
        df_all.to_csv(f"{input_path}/synthetic_data_factory_{good_ratio}_{bad_ratio}_v{version}_{label}.csv", index=False)
    else:
        df_all = pd.read_csv(f"{input_path}/synthetic_data_factory_{good_ratio}_{bad_ratio}_v{version}_{label}.csv")
    
    defect_matrix = generate_defect_cause_matrix(data_matrix=df_all)

    add_interaction_bonus(defect_matrix, rule_interaction)

    threshold = ground_truth_algorithm(defect_matrix)

    defect_matrix = defect_matrix.reset_index(drop=True)

    # 1. Length of defective samples after threshold
    num_bad = defect_matrix["defect"].value_counts().get(1, 0)
    # 2. Calculate percentage of defect rows
    failure_percentage = (num_bad / defect_matrix.shape[0]) * 100
    # 3. Print
    print("✅ Number of good samples:", int(N * good_ratio))
    print("⚠️ Number of bad samples:", int(N * bad_ratio))
    print(f"❌ Number of labeled defects: {num_bad} ({failure_percentage:.2f}%)")

    #update thresholds
    try:
        thresholds_df = pd.read_csv(f"{output_path}/thresholds.csv")
        if "Unnamed: 0" in thresholds_df.columns:
            thresholds_df = thresholds_df.drop(columns=["Unnamed: 0"])
    except pd.errors.EmptyDataError:
        header = ['factory_data_version', 'rbi_threshold', 'rule_interaction', 'total_products']
        thresholds_df = pd.DataFrame(columns=header)
    # Define the new row (dict for clarity)
    new_row = {
        "factory_data_version": f"{good_ratio}_{bad_ratio}_v{version}_{N}",
        "rbi_threshold": float(threshold),
        "rule_interaction": rule_interaction,
        "total_products": N,
    }

    # Check if factory_data_version already exists
    mask = thresholds_df["factory_data_version"] == new_row["factory_data_version"]

    if mask.any():
        # Update existing row
        thresholds_df.loc[mask, :] = pd.DataFrame([new_row])
    else:
        # Append new row
        thresholds_df = pd.concat([thresholds_df, pd.DataFrame([new_row])], ignore_index=True)
    thresholds_df.to_csv(f"{output_path}/thresholds.csv")
    defect_matrix.to_csv(f"{output_path}/defect_cause_matrix_{good_ratio}_{bad_ratio}_v{version}_{label}.csv")