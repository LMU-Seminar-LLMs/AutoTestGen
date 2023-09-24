import sqlite3, json, os
from .constants import MODELS

class DBManager:
    """Class for managing operations on the database."""

    def __init__(self, db_path):
        """Initialize DBManager object.
        Args:
            db_path (str): path to the database file.
        """
        self.conn = self.connect_to_db(db_path)

    def connect_to_db(self, db_path: str) -> sqlite3.Connection:
        """
        Establishes connection to the database. If db doesn't exist,
        creates one and adds tables.

        Args:
            db_path (str): path to the database file.
        
        Returns:
            sqlite3.Connection: connection to the database.
        """
        db_exists = os.path.isfile(db_path)
        self.conn = sqlite3.connect(db_path)
        if not db_exists:
            self.create_tables()
        return self.conn

    def create_tables(self) -> None:
        """Creates database tables if they don't exist yet."""
        cursor = self.conn.cursor()
        try:
            # Tests Table
            cursor.execute(
                """
                CREATE TABLE tests (
                    id INTEGER PRIMARY KEY,
                    module TEXT,
                    class TEXT,
                    object TEXT,
                    history TEXT,
                    test TEXT,
                    metadata TEXT
                )
                """
            )
            # Token-usage Table
            cursor.execute(
                """
                CREATE TABLE token_usage (
                    model TEXT,
                    input_tokens INTEGER,
                    output_tokens INTEGER
                )
                """
            )
            for model in MODELS:
                cursor.execute(
                    """
                    INSERT INTO token_usage
                    (model, input_tokens, output_tokens)
                    VALUES (?, ?, ?)
                    """,
                    (model, 0, 0)
                )
        except Exception as e:
            os.remove("autotestgen.db")
            self.conn.close()
            raise e
        finally:
            cursor.close()
        self.conn.commit()

    def update_token_count(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int
    ) -> None:
        """Updates token count for the model.
        Args:
            model (str): name of the model.
            input_tokens (int): number of input tokens to increment by.
            output_tokens (int): number of output tokens to increment by.
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE token_usage
                SET input_tokens=input_tokens+?, output_tokens=output_tokens+?
                WHERE model=?
                """,
                (input_tokens, output_tokens, model)
            )
        finally:
            cursor.close()
        self.conn.commit()

    def get_row_from_db(self, id: int) -> tuple:
        """Returns data from the database.

        Args:
            id (int): id of the test.
        
        Returns:
            tuple: Single row from the db representing single test.
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT * FROM tests WHERE id=?", (id,))
            data = cursor.fetchone()
        finally:
            cursor.close()
        return data
        
    def get_class_tests(self, class_name: str) -> list:
        """Returns all tests for the class from the database.

        Args:
            class_name (str): name of the class.
        
        Returns:
            list: data from the database.
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT * FROM tests WHERE class=?", (class_name,))
            data = cursor.fetchall()
        finally:
            cursor.close()
        return data
    
    def get_method_tests(self, class_name: str, method: str) -> list:
        """Returns all tests for the method from the database.

        Args:
            class_name (str): name of the class.
            method (str): name of the method.
        
        Returns:
            list: data from the database.
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "SELECT * FROM tests WHERE class=? AND object=?",
                (class_name, method)
            )
            data = cursor.fetchall()
        finally:
            cursor.close()
        return data
    
    def get_function_tests(self, function_name: str) -> list:
        """Returns all tests for the function from the database.

        Args:
            function_name (str): name of the function.
        
        Returns:
            list: data from the database.
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "SELECT * FROM tests WHERE object=? AND class is NULL",
                (function_name, )
            )
            data = cursor.fetchall()
        finally:
            cursor.close()
        return data
    
    def update_test(self, id: int, test: str, metadata: str) -> None:
        """Updates test in database.

        Args:
            id (int): id of the test.
            test (str): new_test.
            metadata (str): metadata containing test and coverage
                for the new_test (json format)
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "UPDATE tests SET test=?, metadata=? WHERE id=?",
                (test, metadata, id)
            )
        finally:
            cursor.close()
        self.conn.commit()

    def edit_test_in_db(self, id: int, test: str) -> None:
        """Edits existing test in the database.

        Args:
            id (int): id of the test.
            test (str): modified test.
        """
        cursor = self.conn.cursor()
        # Get old test
        data = self.get_row_from_db(id)
        # Edit history
        history: list[dict] = json.loads(data[4])
        history[-1].update({"content": test})
        try:
            cursor.execute(
                "UPDATE tests SET test=?, history=? WHERE id=?",
                (test, json.dumps(history), id)
            )
        finally:
            cursor.close()
        self.conn.commit()
    
    def get_usage_data(self) -> list[tuple]:
        """Returns data from the token_usage table.

        Returns:
            list[tuple]: data from the token_usage table.
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT * FROM token_usage")
            data = cursor.fetchall()
        finally:
            cursor.close()
        return data


    def delete_row_from_db(self, id: int) -> None:
        """Deletes row from the database.

        Args:
            id (int): id of the test.
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("DELETE FROM tests WHERE id=?", (id, ))
        finally:
            cursor.close()
        self.conn.commit()

    def add_tests_to_db(
        self,
        module: str,
        class_name: str,
        object_name: str,
        history: str,
        test: str,
        metadata: str
    ) -> None:
        """
        Adds tests to the database.

        Args:
            module (str): name of the module.
            class_name (str): name of the class.
            object_name (str): name of the object.
            history (str): history of the chat in json format.
            test (str): test to add.
            metadata (str): metadata containing test and coverage
                results in json format.
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO tests
                (module, class, object, history, test, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (module, class_name, object_name, history, test, metadata)
            )
        finally:
            cursor.close()
        self.conn.commit()

    def close_db(self) -> None:
        """Closes connection to the database."""
        self.conn.close()
    

    
