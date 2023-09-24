import secrets
import string
import sqlite3, os

class IDGenerator:
    def __init__(self, length: int=16):
        if not isinstance(length, int):
            raise TypeError("Length must be of type int.")
        if length < 0:
            raise ValueError("length mut be a positive")
        self.length = length


    def generate_id(self) -> str:
        alph = string.ascii_letters + string.digits
        secure_id = ''.join(secrets.choice(alph) for _ in range(self.length))
        return secure_id
    

class FakeBankDataGenerator:
    def __init__(self, num_accounts: int=100):
        self.num_accounts = num_accounts
        self.id_generator = IDGenerator(length=16)
        self.accounts = []

    def generate_accounts(self) -> list[dict]:
        """
        Generate fake bank accounts

        Returns:
            list[dict]: list of dictionaries containing account data.

        Data:
            id: unique id for each account.
            name: name of account holder.
            balance: current balance of account.
            interest_rate: interest rate of account.
            type: type of account (normal or savings).
        """
        for _ in range(self.num_accounts):
            account = {
                "id": self.id_generator.generate_id(),
                "name": secrets.choice(
                    ["John", "Jane", "Joe", "Jill", "Jack", "Jen", "Jim"]
                ),
                "balance": secrets.choice(range(10000)),
                "interest_rate": secrets.choice(range(1, 10)) / 100,
                "type": secrets.choice(["normal", "savings"])
            }
            self.accounts.append(account)
        return self.accounts
    
    def get_account(self, account_id: str) -> dict:
        """Get account by id"""
        ids = [account["id"] for account in self.accounts]
        index = ids.index(account_id)
        return self.accounts[index]


def populate_db(num_accounts: int=100) -> list[dict]:
    """
    Geneate fake bank data and add it to a database
    
    Parameters:
        num_accounts (int): number of accounts to generate
    
    Returns:
        list[dict]: list of accounts
    """
    if not isinstance(num_accounts, int):
        raise ValueError("Number of accounts should be an integer")
    if num_accounts < 1:
        raise ValueError("Number of accounts should be greater than 0")
    db = FakeBankDataGenerator(num_accounts)
    accounts = db.generate_accounts()
    if os.path.exists("bank.db"):
        conn = sqlite3.connect("bank.db")
    else:
        conn = sqlite3.connect("bank.db")
        conn.execute(
            """
            CREATE TABLE accounts (
                id TEXT,
                name TEXT,
                balance REAL,
                interest_rate REAL,
                type TEXT
            )
            """
        )
    for account in accounts:
        conn.execute(
            "INSERT INTO accounts VALUES (?, ?, ?, ?, ?)",
            [*account.values()]
        )
    conn.commit()
    conn.close()
    return db.accounts
