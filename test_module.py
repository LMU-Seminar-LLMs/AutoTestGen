import numpy as np
from sklearn.tree import DecisionTreeClassifier

def calculate_hypotenuse(a, b):
    result = np.sqrt(a**2 + b**2)
    return result

def add_two_numbers(a, b):
    """
    Add two numbers.
    
    Parameters:
        a : number 1
        b : number 2
    """
    return a + b

def CustomSum(values):
    """
    Parameters:
        values: List of values
    Returns:
        Sum of the values in given list.
    """
    result = 0
    for value in values:
        result += value
    return result

class Rectangle:
    def __init__(self, width, height):
        self.width = width
        self.height = height
    
    def area(self):
        return self.width * self.height
    
    def perimeter(self):
        return 2 * (self.width + self.height)
    
    def is_square(self):
        return self.width == self.height
    
class Calculator:
    def add(self, a, b):
        return a + b
    
    def subtract(self, a, b):
        return a - b
    
    def multiply(self, a, b):
        return a * b
    
    def divide(self, a, b):
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a / b
    
def find_max_in_list(lst):
    if not lst:
        raise ValueError("List is empty")
    return max(lst)


class BankAccount:
    def __init__(self, account_holder, balance=0):
        self.account_holder = account_holder
        self.balance = balance
    
    def deposit(self, amount):
        if amount <= 0:
            raise ValueError("Amount must be positive")
        self.balance += amount
    
    def withdraw(self, amount):
        if amount <= 0:
            raise ValueError("Amount must be positive")
        if amount > self.balance:
            raise ValueError("Insufficient funds")
        self.balance -= amount
    
    def get_balance(self):
        return self.balance
    
def bubble_sort(arr):
    n = len(arr)
    for i in range(n):
        for j in range(0, n - i - 1):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
    return arr


class Employee:
    def __init__(self, name, salary):
        self.name = name
        self.salary = salary
    
    def apply_raise(self, raise_percentage):
        if raise_percentage < 0:
            raise ValueError("Raise percentage cannot be negative")
        self.salary *= (1 + raise_percentage / 100)


def apply_filter(image, filter_matrix):
    result = []
    for i in range(len(image)):
        row = []
        for j in range(len(image[i])):
            filtered_value = 0
            for x in range(len(filter_matrix)):
                for y in range(len(filter_matrix[x])):
                    row_idx = i - len(filter_matrix) // 2 + x
                    col_idx = j - len(filter_matrix[x]) // 2 + y
                    if 0 <= row_idx < len(image) and 0 <= col_idx < len(image[i]):
                        filtered_value += image[row_idx][col_idx] * filter_matrix[x][y]
            row.append(filtered_value)
        result.append(row)
    return result

class RandomForestClassifier:
    def __init__(self, num_trees=100, max_depth=None):
        self.num_trees = num_trees
        self.max_depth = max_depth
        self.trees = []
    
    def fit(self, X, y):
        for _ in range(self.num_trees):
            tree = DecisionTreeClassifier(max_depth=self.max_depth)
            tree.fit(X, y)
            self.trees.append(tree)
    
    def predict(self, X):
        predictions = [tree.predict(X) for tree in self.trees]
        result = []
        for i in range(len(X)):
            counts = {}
            for pred in predictions:
                if pred[i] not in counts:
                    counts[pred[i]] = 0
                counts[pred[i]] += 1
            most_common = max(counts, key=counts.get)
            result.append(most_common)
        return result
