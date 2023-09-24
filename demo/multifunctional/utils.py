
from typing import Union
from collections.abc import Sequence
from .algorithms import recursive_factorial

def CustomSum(values: Sequence[float]) -> float:
    """
    Sum values in a sequence.
    
    Parameters:
        values (Sequence[float]): A sequence of numeric values.
    """
    result = 0
    for value in values:
        result += value
    return result

def find_max_in_list(lst: list[float]) -> Union[float, int]:
    """Find the maximum value in a list"""
    if not lst:
        raise ValueError("List is empty")
    largest = lst[0]

    for value in lst:
        if not isinstance(value, (float, int)):
            raise ValueError("List contains non-numeric values")
        if value > largest:
            largest = value
    return largest

def bubble_sort(arr: list[float]) -> list[float]:
    """
    Sort a list of numbers using bubble sort.

    """
    n = len(arr)
    for i in range(n):
        for j in range(0, n - i - 1):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
    return arr

def remove_duplicates(lst: list) -> list:
    """Remove duplicates from a list."""
    result = []
    for value in lst:
        if value not in result:
            result.append(value)
    return result


def apply_filter(
    image: Sequence[Sequence[float]],
    filter_matrix: Sequence[Sequence[float]]
) -> Sequence[Sequence[float]]:
    """
    Performs a convolution on a 2D image using a filter matrix.

    Parameters:
        image (Sequence[Sequence[float]]): A 2D image represented as 
            a list of lists of floats.
        filter_matrix (Sequence[Sequence[float]]): A 2D filter matrix

    Returns:
        Sequence[Sequence[float]]: Convolved image.
    """
    result = []
    for i in range(len(image)):
        row = []
        for j in range(len(image[i])):
            filtered_value = 0
            for x in range(len(filter_matrix)):
                for y in range(len(filter_matrix[x])):
                    row_idx = i - len(filter_matrix) // 2 + x
                    col_idx = j - len(filter_matrix[x]) // 2 + y
                    if (
                        0 <= row_idx < len(image)
                        and 0 <= col_idx < len(image[i])
                    ):
                        filtered_value += (image[row_idx][col_idx]
                                           * filter_matrix[x][y])
            row.append(filtered_value)
        result.append(row)
    return result

def calculate_combination(n: int, k: int) -> int:
    """
    Calculate the combination (n choose k) using factorials.

    Parameters:
        n (int): The total number of items.
        k (int): The number of items to choose.

    Returns:
        int: The combination (n choose k).
    """
    if k < 0 or k > n:
        return 0
    else:
        nom = recursive_factorial(n)
        denom = recursive_factorial(k) * recursive_factorial(n - k)
        return nom // denom


