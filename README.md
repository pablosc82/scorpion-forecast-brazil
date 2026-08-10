# Scorpion envenoming forecasting in Brazil

Public dashboard for short-term forecasting of scorpion envenoming incidence in Brazil.

The interface presents the historical monthly incidence series and six-month forecasts for all 27 Brazilian federative units (UFs). Forecast means and 95% uncertainty intervals can be explored by state and by forecast month on the interactive map.

## Scientific basis

The forecasts are produced by five independent global N-BEATS models, one for each Brazilian macroregion. Forecast uncertainty is represented with Monte Carlo Dropout and 95% prediction intervals.

Martinez et al. (2026). *Deep learning forecasting of scorpion envenoming incidence in Brazil to support early warning and prevention.* **Communications Health** 1, Article 2. [Read the publication](https://www.nature.com/articles/s44528-026-00002-9).

This repository contains only the public dashboard and the data artifacts it displays. Model training, model weights, the operational data updater, and training notebooks are intentionally not included.

## Data sources

The upstream workflow uses monthly state-level scorpion accident counts from DATASUS and annual UF population inputs to calculate monthly incidence per 100,000 inhabitants. This public repository contains the resulting historical incidence series and the latest forecast artifacts used by the dashboard.

## Run locally

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

## Interpretation

Forecasts are intended to support public-health surveillance, early warning, and prevention. They are not deterministic values and should be interpreted together with their 95% uncertainty intervals and local epidemiological context.
