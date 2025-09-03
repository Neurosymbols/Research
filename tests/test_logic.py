import pytest
import numpy as np
from pathlib import Path
import pandas as pd

@pytest.fixture(scope="session")
def matrices():
    p = Path(__file__).parents[2] / "Research" / "app" / "data" / "output" / "epoch3-5"
    blind = pd.read_csv(p / "blind_defect_cause_matrix_0.7_0.3_v1.csv")
    exp   = pd.read_csv(p / "defect_cause_matrix_0.7_0.3_v1_train.csv")
    return blind, exp

def test_flag_count_updates(matrices):
    blind, exp = matrices
    m = min(len(blind), len(exp))
    for i in range(m):
        assert blind.at[i, "flag_count"]  == exp.at[i, "fc_count"]

def test_interaction_updates(matrices):
    blind, exp = matrices
    m = min(len(blind), len(exp))
    for i in range(m):
        assert blind.at[i, "interaction"] == exp.at[i, "interaction"]

def test_rbi_updates(matrices):
    blind, exp = matrices
    m = min(len(blind), len(exp))
    for i in range(m):
        assert np.round(blind.at[i, "rbi"], 2) == np.round(exp.at[i, "rbi_score"],2)

def test_defect_updates(matrices):
    blind, exp = matrices
    m = min(len(blind), len(exp))
    for i in range(m):
        print(i)
        assert blind.at[i, "defect"] == exp.at[i, "defect"]
    
