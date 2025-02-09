import torchvision.transforms as transforms
from PIL import Image

# Mapping from integer to color for Jenga blocks
from environment.environment import MAX_BLOCKS_IN_LEVEL, MAX_LEVEL

INT_TO_COLOR = {0: "y", 1: "b", 2: "g"}


def load_image(filename):
    """
    Loads an image from the specified file.

    Args:
        filename (str): The path to the image file.

    Returns:
        PIL.Image.Image: The loaded image.
    """
    # Open the image file
    image = Image.open(filename)
    return image


def preprocess_image(image):
    """
    Preprocesses the input image by converting it to grayscale, resizing,
    converting to a tensor, and normalizing it.

    Args:
        image (PIL.Image.Image): The image to preprocess.

    Returns:
        torch.Tensor: The preprocessed image as a tensor with a batch dimension.
    """
    preprocess = transforms.Compose([
        transforms.Grayscale(num_output_channels=1),  # Convert to grayscale
        transforms.Resize((128, 64)),  # Resize to 128x64 pixels
        transforms.ToTensor(),        # Convert to tensor
        transforms.Normalize(mean=[0.5], std=[0.5])  # Normalize to [-1, 1]
    ])
    return preprocess(image).unsqueeze(0)  # Add batch dimension


def get_state_from_image(filename):
    """
    Loads the image in the filename and preprocesses the input image by converting it to grayscale, resizing,
    converting to a tensor, and normalizing it.

    Args:
        filename (str): The path to the image file.

    Returns:
        torch.Tensor: The preprocessed image as a tensor with a batch dimension. This image represents the state
                      of Jenga
    """
    return preprocess_image(load_image(filename))


def get_possible_actions(taken_actions=set()):
    """
    Returns a list of possible actions that can be taken in the Jenga game, excluding those that have already been
    taken.

    Each action is represented as a tuple containing the level and color of the block to be removed.

    Args:
        taken_actions (set, optional): A set of actions that have already been taken. Each action in the set is a tuple
                                       of the form (level, color), where `level` is an integer representing the level
                                       of the block in the Jenga tower, and `color` is an integer representing the
                                       color of the block. Defaults to an empty set, meaning no actions have been taken.

    Returns:
        list: A list of possible actions that can be taken, excluding those in `taken_actions`. Each action is a tuple
              of the form (level, color).
    """
    return list({(level, color) for level in range(MAX_LEVEL) for color in range(MAX_BLOCKS_IN_LEVEL)} - taken_actions)


def calculate_reward(action, is_fallen, previous_stability, current_stability):
    """
    Calculates the reward for the agent's action.

    Args:
        action (tuple): The action taken by the agent, including the level and color.
        is_fallen (bool): Whether the tower fell after the action.
        previous_stability (float): Stability before the move.
        current_stability (float): Stability after the move.

    Returns:
        int: The calculated reward, including a penalty if the tower fell.
    """
    level, color = action

    # Base reward based on the level of the block removed
    base_reward = level + (1 if color == "b" else 0)

    # Penalty for making the tower more unstable (greater tilt angle)
    stability_penalty = previous_stability - current_stability if previous_stability else -current_stability

    # Penalty if the tower has fallen
    fall_penalty = -50 if is_fallen else 0

    # Combine the rewards and penalties
    reward = base_reward + stability_penalty + fall_penalty

    return reward
