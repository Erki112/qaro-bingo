import os

bind = "0.0.0.0:" + str(os.environ.get("PORT", 5000))
workers = 4
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2
max_requests = 1000
max_requests_jitter = 100
preload = False
