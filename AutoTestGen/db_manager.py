import sqlite3, json, os
from .constants import MODELS

class DBManager:
    """Class for managing operations on the database."""

    def __init__(self, db_path):
        """
        Initialize DBManager object.
        
        Args:
            db_path (str): path to the database file.
        """
        self.db_path = db_path
        self.conn: sqlite3.Connection = self.connect_to_db()
        self.conn.row_factory = sqlite3.Row

    def connect_to_db(self) -> sqlite3.Connection:
        """
        Establishes connection to the database. If db doesn't exist,
        creates one and adds tables.

        Args:
            db_path (str): path to the database file.
        
        Returns:
            sqlite3.Connection: connection to the database.
        """
        db_exists = os.path.isfile(self.db_path)
        self.conn = sqlite3.connect(self.db_path)
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
            os.remove(self.db_path)
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

    def get_row_by_id(self, id: int) -> sqlite3.Row:
        """
        Returns data from the database.

        Args:
            id (int): id of the test.
        
        Returns:
            sqlite3.Row: Single row from the database.
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT * FROM tests WHERE id=?", (id,))
            data = cursor.fetchone()
        finally:
            cursor.close()
        return data
        
    def get_rows_by_class_name(self, class_name: str) -> list[sqlite3.Row]:
        """
        Returns all tests for the class from the database.

        Args:
            class_name (str): name of the class.
        
        Returns:
            list[sqlite3.Row]: list of rows from the database.
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT * FROM tests WHERE class=?", (class_name,))
            data = cursor.fetchall()
        finally:
            cursor.close()
        return data
    
    def get_rows_by_method_name(
        self,
        class_name: str,
        method: str
    ) -> list[sqlite3.Row]:
        """
        Returns all tests for the method from the database.

        Args:
            class_name (str): name of the class.
            method (str): name of the method.
        
        Returns:
            list[sqlite3.Row]: list of rows from the database.
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
    
    def get_rows_by_function_name(
        self,
        function_name: str
    ) -> list[sqlite3.Row]:
        """
        Returns all tests for the function from the database.

        Args:
            function_name (str): name of the function.
        
        Returns:
            list[sqlite3.Row]: list of rows from the database.
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
    
    def get_module_metadata(self, module_name: str) -> list[sqlite3.Row]:
        """
        Returns the metadata for all tests for the module from db.

        Args:
            module_name (str): name of the module.
        
        Returns:
            list[sqlite3.Row]: list of rows from the database.
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "SELECT metadata FROM tests WHERE module=?",
                (module_name,)
            )
            data = cursor.fetchall()
        finally:
            cursor.close()
        return data
    
    def get_module_tests(self, module_name: str) -> list[sqlite3.Row]:
        """
        Returns all tests together with their ids for the given module.

        Args:
            module_name (str): name of the module.
        
        Returns:
            list[sqlite3.Row]: list of rows from the database.
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "SELECT id, test FROM tests WHERE module=?",
                (module_name,)
            )
            data = cursor.fetchall()
        finally:
            cursor.close()
        return data
    
    def update_test(self, id: int, test: str, metadata: str) -> None:
        """
        Updates test in database.

        Args:
            id (int): id of the test.
            test (str): new test.
            metadata (str): metadata containing test and coverage
                for the new test (json format)
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
        """
        Edits existing test in the database.

        Args:
            id (int): id of the test.
            test (str): modified test.
        """
        cursor = self.conn.cursor()
        # Get old test
        data = self.get_row_by_id(id)
        # Edit history
        history: list[dict] = json.loads(data["history"])
        history[-1].update({"content": test})
        try:
            cursor.execute(
                "UPDATE tests SET test=?, history=? WHERE id=?",
                (test, json.dumps(history), id)
            )
        finally:
            cursor.close()
        self.conn.commit()
    
    def get_usage_data(self) -> list[sqlite3.Row]:
        """
        Returns data from the token_usage table.

        Returns:
            list[sqlite3.Row]: complete token_usage table.
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT * FROM token_usage")
            data = cursor.fetchall()
        finally:
            cursor.close()
        return data


    def delete_row_from_db(self, id: int) -> None:
        """
        Deletes row from the database.

        Args:
            id (int): id of the test.
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("DELETE FROM tests WHERE id=?", (id, ))
        finally:
            cursor.close()
        self.conn.commit()

    def add_test_to_db(
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
    

    
