from datetime import date, timedelta
from types import SimpleNamespace
import pytest
from app.ml import daily_frame, forecast, anomalies


def history(count=60, value=10):
    return [SimpleNamespace(id=i, date=date(2025,1,1)+timedelta(days=i), kwh=value) for i in range(count)]


def test_forward_fill_and_sparse_history():
    rows=history()
    rows.pop(10)
    rows[10].kwh=999
    frame,missing=daily_frame(rows)
    assert missing==1
    assert frame.loc['2025-01-11','kwh']==10 # Does not borrow the future spike.
    with pytest.raises(ValueError):
        daily_frame(history()[::2])


def test_zero_targets_and_anomaly_spike(tmp_path):
    result=forecast(history(value=0),999,tmp_path)
    assert result['metrics']['mape'] is None
    assert result['metrics']['mae']==0
    assert all(p['kwh']==0 for p in result['forecast'])
    rows=history()
    rows[-1].kwh=1000
    assert rows[-1].id in [a['id'] for a in anomalies(rows)['alerts']]


def test_imputed_holdout_targets_are_not_scored(tmp_path):
    rows=history()
    rows.pop(55)
    result=forecast(rows,1000,tmp_path)
    assert result['imputed_days']==1
    assert result['metrics']['test_days']==result['metrics']['test_calendar_days']-1
    assert '2025-02-25' not in [p['date'] for p in result['metrics']['holdout']]
