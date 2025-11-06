# examc/deploy/gunicorn.conf.py
import multiprocessing, os
bind = "0.0.0.0:8000"
workers = int(os.environ.get("WEB_CONCURRENCY", max(2,multiprocessing.cpu_count())))
threads = int(os.environ.get("GUNICORN_THREADS", 1))
timeout = int(os.environ.get("WEB_TIMEOUT", 3600))
graceful_timeout = 60
keepalive = 75
max_requests = 1000
max_requests_jitter = 100
worker_tmp_dir = "/dev/shm"
loglevel = os.environ.get("LOG_LEVEL", "info")
accesslog = "-"
errorlog  = "-"
