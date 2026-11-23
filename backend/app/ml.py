"""Daily forecasting: calendar features and past-only lags; chronological holdout."""
from pathlib import Path
import hashlib
import tempfile
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, IsolationForest
from sklearn.metrics import mean_absolute_error, mean_squared_error


def daily_frame(rows):
    frame = pd.DataFrame([{'date': r.date, 'kwh': r.kwh} for r in rows])
    if frame.empty:
        raise ValueError('Add at least 45 daily readings before training.')
    frame['date'] = pd.to_datetime(frame['date'])
    frame = frame.set_index('date').sort_index().asfreq('D')
    frame['observed'] = frame.kwh.notna()
    missing = int(frame.kwh.isna().sum())
    if frame.kwh.notna().sum() < 45 or missing / len(frame) > .2:
        raise ValueError('Training needs 45 observed days and no more than 20% missing days.')
    # Forward fill uses only earlier observations, including in the holdout.
    frame['kwh'] = frame.kwh.ffill()
    return frame, missing


def features(day, history):
    return [day.day_of_week, day.month, day.day_of_year, history[-1], history[-7], np.mean(history[-7:])]


def forecast(rows, user_id, model_dir, days=7):
    frame, missing = daily_frame(rows)
    values = frame.kwh.to_list()
    x = [features(frame.index[i], values[:i]) for i in range(7, len(values))]
    y = np.array(values[7:])
    split = int(len(y) * .8)
    cache = Path(model_dir)
    cache.mkdir(parents=True, exist_ok=True)
    fingerprint = hashlib.sha256(frame.to_csv().encode()).hexdigest()
    path = cache / f'user_{user_id}.joblib'
    saved = joblib.load(path) if path.exists() else None
    if saved and saved['fingerprint'] == fingerprint:
        model, metrics = saved['model'], saved['metrics']
    else:
        model = RandomForestRegressor(n_estimators=160, min_samples_leaf=2, random_state=42, n_jobs=1)
        model.fit(x[:split], y[:split])
        # Evaluate recursive multi-day forecasts, matching production inference.
        history = values[:split + 7].copy()
        predicted = []
        for day in frame.index[split + 7:]:
            value = max(0., float(model.predict([features(day, history)])[0]))
            predicted.append(value)
            history.append(value)
        observed = frame.observed.iloc[split + 7:].to_numpy()
        actual = y[split:][observed]
        predicted = np.array(predicted)[observed]
        if not len(actual):
            raise ValueError('The evaluation period needs observed readings.')
        nonzero = actual != 0
        metrics = {'mae': float(mean_absolute_error(actual, predicted)),
                   'rmse': float(np.sqrt(mean_squared_error(actual, predicted))),
                   'mape': float(np.mean(np.abs((actual[nonzero] - np.array(predicted)[nonzero]) / actual[nonzero])) * 100) if nonzero.any() else None,
                   'test_days': len(actual), 'test_calendar_days': len(observed), 'train_days': split, 'mape_excluded_zero_days': int((~nonzero).sum()),
                   'holdout': [{'date': d.date().isoformat(), 'actual': float(a), 'predicted': float(p)} for d, a, p in zip(frame.index[split+7:][observed], actual, predicted)]}
        model.fit(x, y)
        with tempfile.NamedTemporaryFile(dir=cache, prefix=f'user_{user_id}_', suffix='.tmp', delete=False) as file:
            temporary = Path(file.name)
        try:
            joblib.dump({'model': model, 'metrics': metrics, 'fingerprint': fingerprint}, temporary)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    history = values.copy()
    result = []
    for day in pd.date_range(frame.index[-1] + pd.Timedelta(days=1), periods=days):
        value = max(0., float(model.predict([features(day, history)])[0]))
        history.append(value)
        result.append({'date': day.date().isoformat(), 'kwh': round(value, 3)})
    return {'forecast': result, 'metrics': metrics, 'imputed_days': missing, 'model': 'Random Forest Regressor', 'last_observed_date': frame.index[-1].date().isoformat()}


def anomalies(rows):
    if len(rows) < 14:
        return {'alerts': [], 'message': 'At least 14 readings are required for anomaly detection.'}
    values = np.array([[r.kwh] for r in rows])
    model = IsolationForest(contamination='auto', random_state=42).fit(values)
    labels = model.predict(values)
    median = float(np.median(values))
    return {'alerts': [{'id': r.id, 'date': r.date.isoformat(), 'kwh': r.kwh, 'direction': 'high' if r.kwh > median else 'low'} for r, label in zip(rows, labels) if label == -1], 'message': 'Unusual readings relative to your history; these are signals to investigate.'}
