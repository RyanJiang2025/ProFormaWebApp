

# How to run locally

```
# optional but recommended
python -m venv venv
. venv/bin/activate
pip install -r requirements.txt
streamlit run src/webapp.py
```

# Internal housekeeping

```
ssh shared@proforma.media.mit.edu
cd /home/shared/ProformaWebApp
git pull
docker compose down && docker compose build && docker compose up -d
```

# Notes

- use `proforma-api` branch for the Dynamic Zoning Slider table (https://github.com/amcarrero/frankeinstein-ui).
