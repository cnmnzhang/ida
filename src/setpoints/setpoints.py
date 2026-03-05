"""Helper functions for preprocessing data from raw to structured"""

import os
import sys

import numpy as np
import pandas as pd

from config import ID_COL, TEST_CODE_COL, TS_COL, VERBOSE

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from models import gmm


def calculate_setpoint(isolated_tests_df, test_code, model="bayesian"):
    setpoint, sigma, _ = gmm(isolated_tests_df["result_value"].values, window_size=None, num_components=3)
    # prepared_hyperparameters_df_row = prepared_hyperparameters_df[(prepared_hyperparameters_df[TEST_CODE_COL] == test_code) & (prepared_hyperparameters_df[SEX_COL] == isolated_tests_df[SEX_COL].iloc[0]) & (prepared_hyperparameters_df["model"] == "bayesian")].iloc[0].drop(labels=[TEST_CODE_COL, SEX_COL, "model"], axis=0)

    # setpoint, sigma, _ = bayesian(isolated_tests_df["result_value"].values, **prepared_hyperparameters_df_row.to_dict())
    # get the last sigma and calcuate the 95% CI
    sigma = sigma[-1]
    setpoint = setpoint[-1]

    # Return the last setpoint value
    return setpoint, sigma


def _compute_isolated_indexes(x, min_marker_gap=90):
    """
    Gets isolated test indexes given dates x.

    Parameters:
    x : array-like
        A vector of sampling times, converted to a numerical array.

    Returns:
    indexes : Sequence[bool]
        Boolean array indicating isolated tests.
    """
    # Ensure the dates are sorted before calculating differences
    x = pd.to_datetime(x).sort_values().to_numpy()
    x_days = (x - x[0]).astype("timedelta64[D]").astype(int)
    front_gaps = np.diff(x_days, prepend=-np.inf)
    backward_gaps = np.diff(x_days, append=np.inf)
    isolated = (front_gaps > min_marker_gap) & (backward_gaps > min_marker_gap)
    return isolated


def filter_isolated_tests(all_tests: pd.DataFrame, id_col=ID_COL, ts_col=TS_COL) -> pd.DataFrame:
    """
    Get isolated tests from a DataFrame of tests.

    Parameters:
    all_tests : DataFrame
        A DataFrame with columns 'test_code', 'epic_pat_id', 'result_value', and 'result_date'.
    ts_col : str
        The column name of the timestamp.

    Returns:
    isolated_tests : DataFrame
        A DataFrame with isolated tests.
    """
    preprocessed_df = _preprocess_df(all_tests, id_col, ts_col)

    # check that processed_df is not empty
    if preprocessed_df.empty:
        raise ValueError("preprocessed_df is empty after preprocessing.")

    # Group by patient ID and get isolated tests

    isolated_tests_list = []
    for _, df2 in preprocessed_df.groupby(id_col):
        # Get isolated tests
        indexes: pd.Index = _compute_isolated_indexes(df2[ts_col], min_marker_gap=90)
        df3: pd.DataFrame = df2.loc[indexes]
        isolated_tests_list.append(df3)  # Collect DataFrames in a list

    isolated_tests = pd.concat(isolated_tests_list, ignore_index=True)  # Concatenate once
    return isolated_tests


def _preprocess_df(all_tests: pd.DataFrame, id_col=ID_COL, ts_col=TS_COL) -> pd.DataFrame:
    """
    Preprocess the input DataFrame to clean and sort.
    """
    preprocessed_df = all_tests.copy()
    preprocessed_df[ts_col] = pd.to_datetime(preprocessed_df[ts_col], errors="coerce")

    # Drop rows with NaT in the timestamp column
    preprocessed_df = preprocessed_df.dropna(subset=[ts_col])

    # Drop duplicates and sort
    preprocessed_df = preprocessed_df.sort_values(by=[id_col, ts_col]).drop_duplicates(subset=[id_col, ts_col]).reset_index(drop=True)

    return preprocessed_df


def read_data(file_path, id_col=ID_COL, ts_col=TS_COL):
    all_tests = pd.read_csv(file_path, dtype={id_col: str}, parse_dates=[ts_col])
    return all_tests


def print_verbose(*msg, verbose=VERBOSE):
    """
    Print a message if verbose is set to True.
    """
    if verbose:
        print(*msg)


def get_isolated_tests(past_results_df, test_code):
    """Get isolated Hb tests from past results DataFrame."""
    hb_only = past_results_df[past_results_df[TEST_CODE_COL] == test_code]

    if hb_only.empty:
        return None

    # Force result_value to numeric, coerce errors to NaN, drop them
    hb_only["result_value"] = pd.to_numeric(hb_only["result_value"], errors="coerce")
    clean = hb_only.dropna(subset=["result_value"])

    isolated_tests_df = filter_isolated_tests(clean, id_col=ID_COL, ts_col="result_ts")

    if clean.empty:
        return None
    return isolated_tests_df