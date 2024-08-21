import random
import numpy as np
import torch
import torch.nn.functional as F
from torch import optim
from deep_q_learning.deep_q_network import DQN, ReplayMemory

# Mapping from integer to color for Jenga blocks
INT_TO_COLOR = {0: "y", 1: "b", 2: "g"}


class HierarchicalDQNAgent:
    """
    Hierarchical Deep Q-Network (DQN) agent for solving a Jenga game.

    This agent uses two separate DQNs: one for determining the level of the block to remove,
    and another for determining the color of the block to remove. The agent employs an
    epsilon-greedy policy to balance exploration and exploitation during learning.

    Args:
        input_shape (tuple): The shape of the input state (height, width).
        num_actions_level_1 (int): The number of possible actions for selecting the level.
        num_actions_level_2 (int): The number of possible actions for selecting the color.
        lr (float): Learning rate for the optimizer.
        gamma (float): Discount factor for future rewards.
        epsilon_start (float): Initial value for epsilon in the epsilon-greedy policy.
        epsilon_end (float): Minimum value for epsilon after decay.
        epsilon_decay (int): The rate at which epsilon decays.

    Methods:
        select_action(state): Selects an action based on the current state using the epsilon-greedy policy.
        optimize_model(batch_size): Optimizes the policy networks based on a batch of experiences from replay memory.
        update_target_net(): Updates the target networks with the current weights of the policy networks.
    """

    def __init__(self, input_shape, num_actions_level_1, num_actions_level_2,
                 lr=1e-4, gamma=0.99, epsilon_start=1.0, epsilon_end=0.1,
                 epsilon_decay=5000):
        """
        Initializes the HierarchicalDQNAgent.

        Args:
            input_shape (tuple): The shape of the input state (height, width).
            num_actions_level_1 (int): The number of possible actions for selecting the level.
            num_actions_level_2 (int): The number of possible actions for selecting the color.
            lr (float): Learning rate for the optimizer.
            gamma (float): Discount factor for future rewards.
            epsilon_start (float): Initial value for epsilon in the epsilon-greedy policy.
            epsilon_end (float): Minimum value for epsilon after decay.
            epsilon_decay (int): The rate at which epsilon decays.
        """
        self.gamma = gamma
        self.epsilon = epsilon_start
        self.epsilon_end = epsilon_end
        self.epsilon_decay = epsilon_decay
        self.steps_done = 0

        # DQNs for level and color selection
        self.policy_net_level_1 = DQN(input_shape, num_actions_level_1)
        self.policy_net_level_2 = DQN(input_shape, num_actions_level_2)
        self.target_net_level_1 = DQN(input_shape, num_actions_level_1)
        self.target_net_level_2 = DQN(input_shape, num_actions_level_2)

        # Load policy network weights into target networks
        self.target_net_level_1.load_state_dict(self.policy_net_level_1.state_dict())
        self.target_net_level_2.load_state_dict(self.policy_net_level_2.state_dict())

        # Set target networks to evaluation mode
        self.target_net_level_1.eval()
        self.target_net_level_2.eval()

        # Optimizers for the policy networks
        self.optimizer_level_1 = optim.Adam(self.policy_net_level_1.parameters(), lr=lr)
        self.optimizer_level_2 = optim.Adam(self.policy_net_level_2.parameters(), lr=lr)

        # Replay memory to store experiences
        self.memory = ReplayMemory(10000)

    def select_action(self, state):
        """
        Selects an action based on the current state using the epsilon-greedy policy.

        Args:
            state (torch.Tensor): The current state of the environment.

        Returns:
            tuple: A tuple containing the selected level and color of the block to remove.
        """
        self.steps_done += 1
        # Update epsilon for exploration-exploitation trade-off
        self.epsilon = self.epsilon_end + (self.epsilon - self.epsilon_end) * \
            np.exp(-1. * self.steps_done / self.epsilon_decay)
        print(self.epsilon)

        # Choose action based on epsilon-greedy policy
        if random.random() > self.epsilon:
            with torch.no_grad():
                return self.policy_net_level_1(state).argmax(dim=1).item(), \
                       INT_TO_COLOR[self.policy_net_level_2(state).argmax(dim=1).item()]
        else:
            print("Exploring")
            return random.randrange(0, 9), INT_TO_COLOR[random.randrange(0, 2)]

    def optimize_model(self, batch_size):
        """
        Optimizes the policy networks based on a batch of experiences from replay memory.

        Args:
            batch_size (int): The number of experiences to sample from replay memory for training.
        """
        if len(self.memory) < batch_size:
            return

        # Sample a batch of transitions from replay memory
        transitions = self.memory.sample(batch_size)
        batch_state, batch_action, batch_reward, batch_next_state, batch_done = zip(*transitions)

        # Convert batches to tensors
        batch_state = torch.cat(batch_state)
        batch_reward = torch.tensor(batch_reward)
        batch_next_state = torch.cat(batch_next_state)
        batch_done = torch.tensor(batch_done, dtype=torch.float32)

        # Split actions into separate tensors for level and color
        batch_action_level = torch.tensor([action[0] for action in batch_action]).unsqueeze(1)
        batch_action_color = torch.tensor([action[1] for action in batch_action]).unsqueeze(1)

        # Calculate current Q-values for both levels and colors
        current_q_values_level_1 = self.policy_net_level_1(batch_state).gather(1, batch_action_level)
        next_q_values_level_1 = self.target_net_level_1(batch_next_state).max(1)[0].detach()

        current_q_values_level_2 = self.policy_net_level_2(batch_state).gather(1, batch_action_color)
        next_q_values_level_2 = self.target_net_level_2(batch_next_state).max(1)[0].detach()

        # Calculate expected Q-values using the Bellman equation
        expected_q_values_level_1 = (next_q_values_level_1 * self.gamma * (1 - batch_done)) + batch_reward
        expected_q_values_level_2 = (next_q_values_level_2 * self.gamma * (1 - batch_done)) + batch_reward

        # Compute the loss for both levels and colors
        loss_level_1 = F.mse_loss(current_q_values_level_1, expected_q_values_level_1.unsqueeze(1))
        loss_level_2 = F.mse_loss(current_q_values_level_2, expected_q_values_level_2.unsqueeze(1))

        # Backpropagate the loss and update the network weights
        self.optimizer_level_1.zero_grad()
        self.optimizer_level_2.zero_grad()
        loss_level_1.backward()
        loss_level_2.backward()
        self.optimizer_level_1.step()
        self.optimizer_level_2.step()

    def update_target_net(self):
        """
        Updates the target networks with the current weights of the policy networks.
        """
        self.target_net_level_1.load_state_dict(self.policy_net_level_1.state_dict())
        self.target_net_level_2.load_state_dict(self.policy_net_level_2.state_dict())
