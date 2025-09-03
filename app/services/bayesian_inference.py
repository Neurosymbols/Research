''' Bayesian inference for solder bridging '''

import pandas as pd
import numpy as np
import json
import random

from pgmpy.models import DiscreteBayesianNetwork
from pgmpy.factors.discrete import TabularCPD
from pgmpy.inference import VariableElimination
from sklearn.metrics import confusion_matrix
from app.services.utils import get_failure_cause_concepts
from app.tests import compute_evaluation_matrix

#program variables
overall_rule_firing_probs = {}
rule_confusion_matrix = {}
defect_prior = None
rule_priors = None
bayesian_net = None
strong, dead, moderate = [], [], []


# def generate_panels():
#     #this function accounts for data capture, logical flags, and evidence pull steps
#     fmrs_obj = json.load(open(fmrs))
#     fc_probs = []
#     n_rules = 30
#     n_samples = 10
#     fcs= get_failure_cause_concepts(fmrs_obj)
#     for fc_name, fc_data in fcs.items():
#         fc_probs.append(overall_rule_firing_probs[fc_data['id']])
#     # Initialize empty panel array
#     # each row is product and each column is rule
#     fake_panels = np.zeros((n_samples, n_rules), dtype=int)
#     for i, p in enumerate(fc_probs):
#         #bernoulli trial
#         fake_panels[:, i] = np.random.binomial(1, p, size=n_samples)
#     print(fake_panels)
#     return fake_panels

# def generate_panels():
#     #this function accounts for data capture, logical flags, and evidence pull steps
#     fmrs_obj = json.load(open(fmrs))
#     n_rules = 30
#     n_samples = 30
#     fcs= get_failure_cause_concepts(fmrs_obj)
#     # Initialize empty panel array
#     # each row is product and each column is rule
#     fake_panels = np.zeros((n_samples, n_rules), dtype=int)
#     for i, p in enumerate(fcs.keys()):
#         #bernoulli trial
#         fake_panels[:, i] = np.random.choice([0, 1], size=n_samples)
#     return fake_panels

# def generate_panels():
#     fmrs_obj = json.load(open(fmrs))
#     n_rules = 30
#     n_samples = 30
#     fcs = list(get_failure_cause_concepts(fmrs_obj).keys())

#     fake_panels = np.zeros((n_samples, n_rules), dtype=int)

#     strong_idx = [i for i, fc in enumerate(fcs) if fc in strong]
#     dead_idx = [i for i, fc in enumerate(fcs) if fc in dead]
#     moderate_idx = [i for i in range(n_rules) if i not in strong_idx and i not in dead_idx]

#     for row in range(n_samples):
#         # how many strong rules to fire in this panel (60–100%)
#         k = random.randint(int(0.5*len(strong_idx)), len(strong_idx))
#         fired_strongs = random.sample(strong_idx, k)

#         # set selected strong rules to 1
#         fake_panels[row, fired_strongs] = 1

#         # for the rest (non-strong rules), pick random 0/1
#         for j in moderate_idx:
#             fake_panels[row, j] = np.random.choice([0, 1])

#     return fake_panels

def generate_panels(test_panel_path):
    test_panels_df = pd.read_csv(test_panel_path)
    # Select only columns starting with "FC"
    fc_cols = [col for col in test_panels_df.columns if col.startswith("FC")]
    # Extract rows as list of lists
    fc_data = test_panels_df[fc_cols].values.tolist()
    return fc_data

def calculate_defect_prior(smoothing, train_dcm):
    #smoothing variables laplace
    #alpha: where the middle of the data is.
    #beta: how spread out or consistent the data is around that middle.
    # if D == 0 or D == N, probability will be either 0 or 1 which is too rigid, given our data is limited. This makes model overconfident(#TODO: understand overconfidence)
    # Smoothing fixes this by adding "pseudo-counts" before dividing.
    # consider A as "pseudo-successes" and B as "pseudo-failures"
    global defect_prior
    A = 0.5 if smoothing else 0
    B = 0.5 if smoothing else 0
    df = pd.read_csv(train_dcm)
    D = (df["defect"] == 1).sum()
    N = df["defect"].count()
    defect_prior = (A + D) / (A + B + N)
    # print(f"defect prior: {defect_prior}")

def calculate_rule_priors(smoothing, train_dcm, output_path, train_dist):
    global overall_rule_firing_probs, rule_priors
    Ai1 = 0.5 if smoothing else 0
    Bi1 = 0.5 if smoothing else 0
    Ai0 = 0.5 if smoothing else 0
    Bi0 = 0.5 if smoothing else 0
    df = pd.read_csv(train_dcm)
    fc_cols = df[[col for col in df.columns if col.startswith("FC")]]
    # fc is 1 when defect is 1
    fc_i1 = {} #true positive rate (recall)
    # fc is 1 when defect is 0
    fc_i0 = {} #false postive rate
    rule_priors = {}
    for col in fc_cols:
        boolean_df_col = (df[col] > 0).astype(int)
        overall_rule_firing_probs[col] = float(boolean_df_col.mean())
        #calculating conditional probs using sklearn without smoothing
        tn, fp, fn, tp = confusion_matrix(df['defect'], boolean_df_col).ravel()
        recall = tp / (tp + fn) if (tp+fn) > 0 else 0
        fpr = fp / (fp + tn) if (fp+tn) > 0 else 0
        if recall >= 0.95 and fpr > 0:
            strong.append(col)
        elif recall == 0 and fpr == 0:
            dead.append(col)
        else:
            moderate.append(col)
        fc_i1[col] = float( (Ai1 + tp) / (Ai1 + Bi1 + tp + fn))
        fc_i0[col] = float( (Ai0 + fp) / (Ai0 + Bi0 + fp + tn))
        rule_confusion_matrix[col] = [int(tn), int(fp), int(fn), int(tp)]

        #calculating conditional probs manually
        # defect_count = float(df[df['defect']==1].shape[0])
        # tp_count = float(df[(df[col] > 0) & (df["defect"] == 1)].shape[0])
        # fc_i1[col] = round((tp_count/defect_count),4)

        # fn_count = float(df[(df[col] == 0) & (df["defect"] == 1)].shape[0])
        # fc_i0[col] = round((fn_count/defect_count),4)
    for col, val in fc_i1.items():
        assert col in fc_i0, "inconsistent matrices found"
        if col not in rule_priors:
            rule_priors[col] = {}
        rule_priors[col]["fc_i1"] = val
        rule_priors[col]["fc_i0"] = fc_i0[col]
    with open(f"{output_path}/rule_priors_smoothing_{train_dist}.json", "w") as f:
        json.dump(rule_priors, f, indent=2)

    # print(f"likelihood of rules firing when defect is there :{fc_i1}")
    # print(f"likelihood of rules firing when defect is not there :{fc_i0}")
    # print(f"rule priors: {rule_priors}")

def creat_bayesian_net():
    # Define structure: Bridge → all rules
    global bayesian_net
    edges = [("Bridge", k) for k in overall_rule_firing_probs]
    bayesian_net = DiscreteBayesianNetwork(edges)
    print(f"defect priors: {defect_prior}")
    cpd_bridge = TabularCPD(
        variable='Bridge',
        variable_card=2,
        values=[[1 - defect_prior], [defect_prior]],
        state_names={'Bridge': ['False', 'True']}
    )
    assert list(overall_rule_firing_probs.keys()) == list(rule_priors.keys()), "keys or their order is different"
    cpd_rules = []
    for fc, priors in rule_priors.items():
        cpd = TabularCPD(
            variable=fc,
            variable_card=2,
            values = [
                [1-priors['fc_i0'], 1-priors['fc_i1']],
                [priors['fc_i0'], priors['fc_i1']]
            ],
            evidence=['Bridge'],
            evidence_card=[2],
            state_names={fc: ['False', 'True'], 'Bridge': ['False', 'True']}
        )
        cpd_rules.append(cpd)
    bayesian_net.add_cpds(cpd_bridge, *cpd_rules)
    # Validate
    print("Model valid?", bayesian_net.check_model())

def run_inference(test_panels_path, output_path, train_dist):
    panels = generate_panels(test_panels_path)
    bridge_data = []
    for p in panels:
        evidence = {f"FC{i+1}": ("True" if val > 0 else "False")
                for i, val in enumerate(p)}
        strong_fired = [k for k in evidence if k in strong and evidence[k] == "True"]
        moderate_fired = [k for k in evidence if k in moderate and evidence[k] == "True"]
        # print(f"#######panel {i+1}#######")
        # print(f"strong fired: {[k for k in evidence if k in strong and evidence[k] == "True"]}")
        # print(f"moderate fired: {[k for k in evidence if k in moderate and evidence[k] == "True"]}")
        # print(f"evidence: {evidence}")
        # Create inference engine
        # TODO: understand why variable elimination?
        infer = VariableElimination(bayesian_net)
        # Query the posterior probability of Bridge given evidence
        posterior = infer.query(
            variables=["Bridge"],
            evidence=evidence
        )
        p_true  = posterior.values[1]
        evidence['bridge_probability'] = p_true
        evidence['strong_fired'] = ", ".join(strong_fired)
        evidence['moderate_fired'] = ", ".join(moderate_fired)
        bridge_data.append(evidence)
        get_likelihood_ratios_pgmpy(bayesian_net, p)
    df = pd.DataFrame(bridge_data)
    df.to_csv(f"{output_path}/bayesian_output_{train_dist}.csv")

def get_likelihood_ratios_pgmpy(model, panel):
    for fc, val in zip(rule_priors.keys(), panel):
        cpd = model.get_cpds(fc)
        # rows: [False, True], cols: [Bridge=False, Bridge=True]
        p_true_b0 = cpd.values[1,0]
        p_true_b1 = cpd.values[1,1]
        p_false_b0 = cpd.values[0,0]
        p_false_b1 = cpd.values[0,1]

        if val == 1:  # Rule fired
            lr = p_true_b1 / p_true_b0 if p_true_b0 > 0 else float("inf")
            # print(f"{fc} fired=True → LR={lr}")
        else:  # Rule did not fire
            lr = p_false_b1 / p_false_b0 if p_false_b0 > 0 else float("inf")
            # print(f"{fc} fired=False → LR={lr}")

def ground_truth_testing(test_panels_path, output_path, train_dist):
    gt = pd.read_csv(test_panels_path)
    pt = pd.read_csv(f"{output_path}/bayesian_output_{train_dist}.csv")
    true = gt['defect'].to_list()
    pred = (pt["bridge_probability"] >= 0.85).astype(int).tolist()
    compute_evaluation_matrix(true, pred, f"{output_path}/bayesian_output_{train_dist}_EM")

def implement_bayesian_inference(
    train_dcm,
    test_panels,
    output_path,
    train_dist
):
    calculate_defect_prior(smoothing=True, train_dcm=train_dcm)
    calculate_rule_priors(
        smoothing=True, 
        train_dcm=train_dcm, 
        output_path=output_path,
        train_dist=train_dist
    )
    creat_bayesian_net()
    run_inference(test_panels, output_path, train_dist)
    ground_truth_testing(test_panels, output_path, train_dist)