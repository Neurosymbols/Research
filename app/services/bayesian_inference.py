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
from app.tests.tests import compute_evaluation_matrix

#program variables
overall_rule_firing_probs = {}
rule_confusion_matrix = {}
defect_prior = None
rule_priors = None
bayesian_net = None
strong, dead, moderate = [], [], []


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
    Ai1 = 0.5 if smoothing else 0 #defect occurs rule fires
    Bi1 = 0.5 if smoothing else 0 #defect occurs rule does not fire
    Ai0 = 0.5 if smoothing else 0 #defect not occurs rule fires
    Bi0 = 0.5 if smoothing else 0 #defect not occurs rule does not fire
    df = pd.read_csv(train_dcm)
    fc_cols = df[[col for col in df.columns if col.startswith("FC")]]
    # fc(rule) fires when defect is 1
    fc_i1 = {} #true positive rate (recall) --> Ai1
    # fc(rule) fires when defect is 0 --> Ai0
    fc_i0 = {} #false postive rate
    rule_priors = {}
    for col in fc_cols:
        #get me rows where fc is 1
        boolean_df_col = (df[col] > 0).astype(int)
        #overall probability of rule firing
        overall_rule_firing_probs[col] = float(boolean_df_col.mean())
        #calculating conditional probs using sklearn without smoothing
        #df['defect'] --> truth
        #boolean_df_col --> pred
        print(col)
        print(confusion_matrix(df['defect'], boolean_df_col, labels=[0, 1]).ravel())
        #tn: when defect does not occur rule does not fire
        #tp: when defect occurs rule fires
        #fn: when defect occurs rule does not fire
        #fp: when defect not occurs rule fires    
        tn, fp, fn, tp = confusion_matrix(df['defect'], boolean_df_col, labels=[0, 1]).ravel()
        recall = tp / (tp + fn) if (tp+fn) > 0 else 0
        fpr = fp / (fp + tn) if (fp+tn) > 0 else 0
        if recall >= 0.95 and fpr > 0:
            strong.append(col)
        elif recall == 0 and fpr == 0:
            dead.append(col)
        else:
            moderate.append(col)
        rule_confusion_matrix[col] = [int(tn), int(fp), int(fn), int(tp)]

        #prior calculation for the rule
        fc_i1[col] = float( (Ai1 + tp) / (Ai1 + Bi1 + tp + fn))
        fc_i0[col] = float( (Ai0 + fp) / (Ai0 + Bi0 + fp + tn))

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
        rule_priors[col]["fc0_i1"] = 1 - val
        rule_priors[col]["fc_i0"] = fc_i0[col]
        rule_priors[col]["fc0_i0"] = 1 - fc_i0[col]
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

def ground_truth_testing(
    test_panels_path, 
    output_path, 
    train_dist, 
    defect_probability
):
    gt = pd.read_csv(test_panels_path)
    pt = pd.read_csv(f"{output_path}/bayesian_output_{train_dist}.csv")
    true = gt['defect'].to_list()
    pred = (pt["bridge_probability"] >= defect_probability).astype(int).tolist()
    compute_evaluation_matrix(true, pred, f"{output_path}/bayesian_output_{train_dist}_EM")

def implement_bayesian_inference(
    train_dcm,
    test_panels,
    output_path,
    train_dist,
    defect_probability
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
    ground_truth_testing(test_panels, output_path, train_dist, defect_probability)