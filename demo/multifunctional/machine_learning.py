import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.exceptions import NotFittedError

class LinearModel:
    def __init__(self):
        self.model = LinearRegression()
        self.is_fitted = False

    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        """Fit the model to the data."""
        # Check if X and y have the right shape
        if len(X.shape) != 2 or len(y.shape) != 1:
            raise ValueError(
                ("Parameters X and y should have shapes (n_samples, n_features)"
                "and (n_samples), respectively")
            )
        # Fit model and set fitting state to True
        self.model.fit(X, y)
        self.is_fitted = True

    def predict(self, X: np.ndarray):
        """Predict using already fitted model."""
        # Check if model has been fitted before predicting
        if not self.is_fitted:
            raise NotFittedError(
                "This model is not fitted yet. Call 'fit' first"
            )

        # Check if X has the right shape
        if len(X.shape) != 2:
            raise ValueError(
                "Parameter X should have shape (n_samples, n_features)"
            )
        if X.shape[1] != self.model.coef_.shape[0]:
            raise ValueError(
                ("Parameter X should have the same number of features as the"
                "fitted model")
            )
        return self.model.predict(X)

    def coef(self):
        # Check if model has been fitted before returning coefficients
        if not self.is_fitted:
            raise NotFittedError(
                "This model is not fitted yet, call 'fit' method first."
            )
        return self.model.coef_
