"""Independent, reproducible sample evaluation; no account data is created."""
import argparse
import json
from types import SimpleNamespace
from datetime import date
import pandas as pd
from app.ml import forecast

parser = argparse.ArgumentParser()
parser.add_argument('csv')
parser.add_argument('--model-dir', default='models_cache/evaluation')
args = parser.parse_args()
data = pd.read_csv(args.csv)
rows = [SimpleNamespace(date=date.fromisoformat(r.date), kwh=float(r.kwh)) for r in data.itertuples()]
print(json.dumps(forecast(rows, 'sample', args.model_dir), indent=2))
