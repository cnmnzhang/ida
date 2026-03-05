import warnings

import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.mixture import GaussianMixture

import classes.mylogger as mylogger


def gmm(
    x,
    window_size=None,
    num_components=3,
):
    """Fit Gaussian Mixture Models to the input data and compute statistical metrics.

    This function fits Gaussian Mixture Models (gmm) with 1 to 3 components to subsets of the input data.
    It calculates the mean and standard deviation of the fitted models,
    returning these values as arrays. assessing the best model based on the Akaike Information Criterion (AIC).

    Args:
        x (np array): Input data for fitting the gmms.

    Returns:
        tuple: A tuple containing three numpy arrays:
            - mus: The means of the fitted models.
            - sigma_means: The standard deviations of the fitted models.
            - sigma_modes: The modes of the fitted models.
    """

    # Account for how we will skip fitting the first point

    mus = [x[0]]
    sigma_means = [0]
    sigma_modes = [0]
    num_components_list = []
    window_size = int(window_size) if window_size else None

    x = np.array(x)
    lb = 0
    # Think of i as the number of observations
    for i in range(2, len(x) + 1):
        if window_size:
            lb = max(0, i - window_size)
        x_subset = x[lb:i]
        unique_points = len(np.unique(x_subset))
        x_subset_mat = x[:i].reshape(-1, 1)
        mdl = [None] * num_components  # Holds mixture components
        aic = np.full(num_components, np.nan)  # Holds AIC values for each model
        setpoint, setpoint_cv = None, None

        # Try a 1, 2, and 3-component model fit
        for k in range(1, num_components + 1):
            # Skip if the number of components is greater than the number of data points in the subset,
            # as there are not enough data points to form a valid model with that many components.
            if k >= unique_points:
                continue
            try:
                # Catch convergence warnings
                with warnings.catch_warnings():
                    warnings.filterwarnings("error", category=ConvergenceWarning)
                    gm = GaussianMixture(n_components=k, max_iter=300, reg_covar=0.001)
                    gm.fit(x_subset_mat)
                    mdl[k - 1] = gm
                    aic[k - 1] = gm.aic(x_subset_mat)
            except ConvergenceWarning as cw:
                mylogger.logger.warning("Model with %d components did not converge: %s", k, str(cw))
                # mylogger.logger.info(f"k = {k}, unique_points = {unique_points}")
                # mylogger.logger.info("x:", x_subset)

        # check if aic is populated
        if np.any(np.isfinite(aic)):
            # Select the best model
            min_idx = np.nanargmin(aic)
            best_mdl = mdl[min_idx]
            # get the max proportion of the best model
            mdl_prop = best_mdl.weights_
            # If a 2 or 3 component model produces the best AIC, and has one proportion that is much larger than the others, use it.
            # Otherwise use a 1-component model which is mean of the data
            if (min_idx == 1 and np.max(mdl_prop) > 0.7) or (min_idx == 2 and np.max(mdl_prop) > 0.45):
                max_idx = np.argmax(mdl_prop)
                setpoint = best_mdl.means_[max_idx].flatten()[0]
                setpoint_cv = np.sqrt(best_mdl.covariances_[max_idx].flatten()[0]) / best_mdl.means_[max_idx].flatten()[0]

                num_components_list.append(min_idx + 1)
        if not setpoint:
            setpoint = np.mean(x_subset)
            setpoint_cv = np.std(x_subset) / np.mean(x_subset)
            num_components_list.append(1)

        mus.append(setpoint)
        sigma_means.append(setpoint_cv * setpoint)
        sigma_modes.append(setpoint_cv * setpoint)

    # Convert lists to numpy arrays
    mus = np.array(mus)
    sigma_means = np.array(sigma_means)
    sigma_modes = np.array(sigma_modes)

    sigmas = sigma_means

    return mus, sigmas, np.array(num_components_list)

