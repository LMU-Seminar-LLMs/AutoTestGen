from typing import Union
def fibonacci(n: int, memo: set={}) -> int:
    """
    Generate the nth Fibonacci number using memoization.

    Parameters:
        n (int): The index of the Fibonacci number to generate.
        memo (dict): A dictionary to store previously computed 
            Fibonacci numbers for memoization.

    Returns:
        int: The nth Fibonacci number.
    """
    if n in memo:
        return memo[n]
    
    if n <= 1:
        memo[n] = n
    else:
        memo[n] = fibonacci(n - 1, memo) + fibonacci(n - 2, memo)
    
    return memo[n]


def recursive_binary_search(
    arr: list,
    target,
    low:int=0, 
    high:Union[int, None]=None
) -> Union[int, None]:
    """
    Perform a binary search on a sorted array to find the index of
        the target element recursively.

    Parameters:
        arr (list): The sorted array to search in.
        target: The element to search for.
        low (int): The lower index of the search range (default is 0).
        high (int): The upper index of the search range
            (default is None, which is set to len(arr) - 1).

    Returns:
        int: The index of the target element if found, otherwise None.
    """
    if high is None:
        high = len(arr) - 1

    if low > high:
        return None

    mid = (low + high) // 2

    if arr[mid] == target:
        return mid
    elif arr[mid] < target:
        return recursive_binary_search(arr, target, mid + 1, high)
    else:
        return recursive_binary_search(arr, target, low, mid - 1)
    

def recursive_factorial(n: int) -> int:
    """
    Calculate the factorial of a non-negative integer using recursion.

    Parameters:
        n (int): The non-negative int to calculate the factorial of.

    Returns:
        int: The factorial of n.
    """
    if n < 0:
        raise ValueError("n must be non-negative")
    elif n == 0:
        return 1
    else:
        return n * recursive_factorial(n - 1)