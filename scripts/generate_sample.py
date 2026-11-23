"""Create clearly synthetic daily household consumption for academic evaluation."""
import csv
import math
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(42)
root = Path(__file__).resolve().parents[1]
target = root / 'frontend' / 'public' / 'sample-consumption.csv'
target.parent.mkdir(parents=True, exist_ok=True)
with target.open('w', newline='', encoding='utf-8') as file:
    writer = csv.writer(file)
    writer.writerow(['date', 'kwh'])
    for i in range(365):
        day = date(2025, 1, 1) + timedelta(days=i)
        usage = 8 + 2 * math.sin(i / 365 * 2 * math.pi) + (1.5 if day.weekday() >= 5 else 0) + random.gauss(0, .65)
        if i in (65, 140, 270):
            usage += 9
        writer.writerow([day.isoformat(), round(max(0, usage), 3)])
print(target)
