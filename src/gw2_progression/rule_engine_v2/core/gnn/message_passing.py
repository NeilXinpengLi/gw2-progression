from __future__ import annotations

import numpy as np


class MessagePassingLayer:
    def __init__(self, input_dim: int, output_dim: int, activation: str = "relu") -> None:
        self.input_dim = input_dim
        self.output_dim = output_dim
        self.activation = activation
        self.W = np.random.randn(input_dim, output_dim).astype(np.float32) * 0.1
        self.b = np.zeros(output_dim, dtype=np.float32)

    def forward(self, features: np.ndarray, adjacency: np.ndarray) -> np.ndarray:
        degree = np.sum(adjacency, axis=1, keepdims=True)
        degree = np.where(degree < 1e-10, 1e-10, degree)
        degree_inv = 1.0 / np.sqrt(degree)
        norm_adj = adjacency * degree_inv
        norm_adj = norm_adj * degree_inv.T
        messages = norm_adj @ features
        out = messages @ self.W + self.b
        if self.activation == "relu":
            out = np.maximum(out, 0)
        elif self.activation == "sigmoid":
            out = 1.0 / (1.0 + np.exp(-np.clip(out, -100, 100)))
        elif self.activation == "tanh":
            out = np.tanh(out)
        return out

    def update_weights(self, grad_W: np.ndarray, grad_b: np.ndarray, lr: float = 0.01) -> None:
        self.W -= lr * grad_W
        self.b -= lr * grad_b


class MessagePassingNetwork:
    def __init__(self, input_dim: int = 8, hidden_dim: int = 16, output_dim: int = 8, num_layers: int = 3) -> None:
        self.layers: list[MessagePassingLayer] = []
        dims = [input_dim] + [hidden_dim] * (num_layers - 1) + [output_dim]
        for i in range(len(dims) - 1):
            act = "relu" if i < len(dims) - 2 else "sigmoid"
            self.layers.append(MessagePassingLayer(dims[i], dims[i + 1], activation=act))

    def forward(self, features: np.ndarray, adjacency: np.ndarray) -> np.ndarray:
        h = features
        for layer in self.layers:
            h = layer.forward(h, adjacency)
        return h

    def forward_batch(self, graphs: list[tuple[np.ndarray, np.ndarray]]) -> list[np.ndarray]:
        return [self.forward(f, a) for f, a in graphs]
