"""E2E test conftest — disable rate limiting."""

import os

os.environ["RATE_LIMIT_REQUESTS"] = "9999"
