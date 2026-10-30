.PHONY: install db pipeline test notebook dashboard stop
install:
	python -m pip install -r requirements.txt
db:
	docker compose up -d --wait
pipeline:
	python -m src.run_pipeline
test:
	python -m pytest -q
notebook:
	python scripts/execute_notebook.py
dashboard:
	python -m streamlit run dashboard/app.py --server.address 127.0.0.1
stop:
	docker compose stop
