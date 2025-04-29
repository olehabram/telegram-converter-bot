web: gunicorn main_bot:asgi_app -w 1 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --log-level info
