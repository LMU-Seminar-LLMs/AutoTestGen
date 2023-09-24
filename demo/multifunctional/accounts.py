from .id_generator import IDGenerator


class Account:
    def __init__(self, name: str, balance: float, id):
        self._name = name
        self._balance = balance
        self.id_generator = IDGenerator(int=16)
        self._id = self.id_generator.generate_id()
    
    @property
    def balance(self):
        return self._balance

    @balance.setter
    def balance(self, new_balance: float) -> None:
        if not isinstance(new_balance, (int, float)):
            raise ValueError("Balance should be numeric")
        self._balance = new_balance
    
    def __str__(self):
        return f"Account name: {self._name}, balance: {self._balance}"
    
    def deposit(self, amount: float) -> None:
        """Deposit money to account"""
        try:
            self._balance += amount
        except:
            raise ValueError("Amount should be numeric")
        
    def withdraw(self, amount: float) -> None:
        """Withdraw money from account"""
        if self._balance - amount < 0:
             raise ValueError("Not enough money in Account")
        self._balance -= amount

class SavingsAccount(Account):
    def __init__(self, name: str, balance: float, interest_rate: float):
        super().__init__(name, balance)
        self._interest_rate = interest_rate
    
    def withdraw(self) -> None:
        raise AttributeError("Cannot withdraw from Savings Account")
    
    def apply_interest(self):
        self._balance += self._balance * self._interest_rate
    
    def __str__(self):
        return (
            f"Savings Account: {self._name}, "
            f"balance: {self._balance}, "
            f"interest: {self._interest_rate}"
        )