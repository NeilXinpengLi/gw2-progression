"""GW2 Progression Training Service — standalone Docker training worker.

This is the REAL training engine that replaces the deterministic ModelTrainer facade.
It runs as a separate Docker container, subscribed to training data via Redis streams.

Architecture:
  Expert AI System (app/worker)
    -> publishes training events to Redis stream "training:events"
  Training Service (this module)
    <- subscribes to Redis stream, collates batches, runs sklearn training
    -> saves model artifacts to configurable checkpoint directory
    -> publishes model metadata to model registry (Postgres/JSON)
"""

from __future__ import annotations
