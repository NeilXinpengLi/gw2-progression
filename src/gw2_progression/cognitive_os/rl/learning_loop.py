from __future__ import annotations

from typing import Any, Callable

from gw2_progression.cognitive_os.rl.policy import RLPolicy
from gw2_progression.cognitive_os.rl.reward import RewardFunction


class LearningLoop:
    """Self-improving closed loop system.

    1. simulate world (OOSK)
    2. generate decisions (BORS)
    3. compute reward
    4. update policy (RL)
    5. update graph reasoning
    6. improve LLM reasoning
    7. repeat
    """

    def __init__(
        self,
        policy: RLPolicy | None = None,
        reward_fn: RewardFunction | None = None,
    ) -> None:
        self.policy = policy or RLPolicy()
        self.reward_fn = reward_fn or RewardFunction()
        self._episodes: int = 0
        self._total_reward: float = 0.0
        self._episode_rewards: list[float] = []
        self._callbacks: dict[str, list[Callable]] = {
            "episode_start": [],
            "step": [],
            "episode_end": [],
            "training_complete": [],
        }

    def on(self, event: str, callback: Callable) -> None:
        if event in self._callbacks:
            self._callbacks[event].append(callback)

    def run_episode(
        self,
        initial_state: dict[str, Any],
        action_sampler: Callable[[dict[str, Any]], list[dict[str, Any]]],
        simulator: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
        max_steps: int = 50,
    ) -> dict[str, Any]:
        self._episodes += 1
        state = dict(initial_state)
        episode_reward = 0.0
        steps_taken = 0
        trajectory: list[dict[str, Any]] = [dict(state)]
        actions_taken: list[dict[str, Any]] = []
        validations: list[list[dict[str, Any]]] = [[]]

        for cb in self._callbacks.get("episode_start", []):
            cb(self._episodes, state)

        for step in range(max_steps):
            available = action_sampler(state)
            if not available:
                break
            action = self.policy.select_action(state, available)
            if action is None:
                break
            next_state = simulator(state, action)
            actions_taken.append(action)
            trajectory.append(dict(next_state))

            components = self.reward_fn.compute(state, next_state, action)
            reward = components.total
            episode_reward += reward
            self._total_reward += reward

            next_available = action_sampler(next_state)
            self.policy.update(state, action, reward, next_state, next_available)

            state = next_state
            steps_taken = step + 1

            val = state.get("_action_validations", [])
            validations.append(list(val) if val else [])

            for cb in self._callbacks.get("step", []):
                cb(step, state, action, reward)

        self._episode_rewards.append(episode_reward)

        for cb in self._callbacks.get("episode_end", []):
            cb(self._episodes, episode_reward, steps_taken)

        return {
            "episode": self._episodes,
            "total_reward": episode_reward,
            "steps": steps_taken,
            "trajectory": trajectory,
            "actions": actions_taken,
            "validations": validations,
            "final_state": state,
        }

    def train(
        self,
        initial_state_factory: Callable[[], dict[str, Any]],
        action_sampler: Callable[[dict[str, Any]], list[dict[str, Any]]],
        simulator: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
        episodes: int = 100,
        max_steps_per_episode: int = 50,
        verbose: bool = True,
    ) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        for ep in range(episodes):
            init_state = initial_state_factory()
            result = self.run_episode(init_state, action_sampler, simulator, max_steps_per_episode)
            results.append(result)
            if verbose and (ep + 1) % 10 == 0:
                avg = self.reward_fn.average_reward(10)
                print(f"  Episode {ep + 1}/{episodes} | reward={result['total_reward']:.3f} | "
                      f"steps={result['steps']} | avg_last10={avg:.3f} | "
                      f"ε={self.policy.epsilon:.3f}")

        for cb in self._callbacks.get("training_complete", []):
            cb(episodes, self._episode_rewards)

        return {
            "episodes": episodes,
            "total_episodes_run": self._episodes,
            "final_avg_reward": self.reward_fn.average_reward(min(50, len(self._episode_rewards))),
            "policy_state": self.policy.to_dict(),
            "reward_history": self.reward_fn.reward_history(),
            "episode_rewards": self._episode_rewards[-min(100, len(self._episode_rewards)):],
        }

    def evaluate(
        self,
        state: dict[str, Any],
        action_sampler: Callable[[dict[str, Any]], list[dict[str, Any]]],
        simulator: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
        max_steps: int = 20,
    ) -> dict[str, Any]:
        old_epsilon = self.policy.epsilon
        self.policy.epsilon = 0.0
        result = self.run_episode(state, action_sampler, simulator, max_steps)
        self.policy.epsilon = old_epsilon
        return result

    def status(self) -> dict[str, Any]:
        return {
            "episodes": self._episodes,
            "total_reward": self._total_reward,
            "average_reward": self.reward_fn.average_reward(),
            "policy": self.policy.to_dict(),
        }
