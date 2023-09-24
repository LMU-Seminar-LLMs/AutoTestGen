import unittest
import json
from AutoTestGen.db_manager import DBManager

class TestDBManager(unittest.TestCase):
    def setUp(self):
        db_path = ":memory:"
        self.db_manager = DBManager(db_path)
        self.db_manager.conn.execute(
            """
            UPDATE token_usage
            SET input_tokens=?, output_tokens=?
            WHERE model=?
            """,
            (100, 200, "gpt-3.5-turbo")
        )
        self.db_manager.conn.commit()
        self.test_data = {
            "module": "AutoTestGen.db_manager",
            "class": "DBManager",
            "object": "connect_to_db",
            "history": '[{"content": "def test_add_test_to_db(self): pass"}]',
            "test": "def test_add_test_to_db(self): pass",
            "metadata": '{"coverage": 80}'
        }
        self.db_manager.add_test_to_db(
            self.test_data["module"],
            self.test_data["class"],
            self.test_data["object"],
            self.test_data["history"],
            self.test_data["test"],
            self.test_data["metadata"]
        )

    def tearDown(self):
        self.db_manager.conn.execute("DROP TABLE IF EXISTS token_usage")
        self.db_manager.conn.execute("DROP TABLE IF EXISTS tests")
        self.db_manager.close_db()

    def test_get_usage_data(self):
        usage_data = self.db_manager.get_usage_data()
        self.assertEqual(usage_data[0]["input_tokens"], 100)
        self.assertEqual(usage_data[0]["output_tokens"], 200)
    
    def test_get_row_by_id(self):
        row = self.db_manager.get_row_by_id(1)
        for key in self.test_data:
            self.assertEqual(row[key], self.test_data[key])

    def test_get_rows_by_class_name(self):
        row = self.db_manager.get_rows_by_class_name("DBManager")
        for key in self.test_data:
            self.assertEqual(row[0][key], self.test_data[key])
    
    def test_get_rows_by_method_name(self):
        row = self.db_manager.get_rows_by_method_name(
            self.test_data["class"],
            self.test_data["object"]
        )
        for key in self.test_data:
            self.assertEqual(row[0][key], self.test_data[key])

    def test_get_rows_by_function_name(self):
        row = self.db_manager.get_rows_by_function_name(
            self.test_data["object"]
        )
        self.assertEqual(row, [])
    
    def test_get_module_metadata(self):
        row = self.db_manager.get_module_metadata(
            self.test_data["module"]
        )
        self.assertEqual(row[0]["metadata"], self.test_data["metadata"])
    
    def test_get_module_tests(self):
        tests = self.db_manager.get_module_tests(
            self.test_data["module"]
        )
        self.assertEqual(tests[0]["id"], 1)
        self.assertEqual(tests[0]["test"], self.test_data["test"])
    
    def test_update_test(self):
        new_test = "def test_update_test(self): pass"
        self.db_manager.update_test(1, new_test, metadata='{"coverage": 100}')
        cursor = self.db_manager.conn.cursor()
        cursor.execute("SELECT * FROM tests WHERE id=?", (1,))
        row = cursor.fetchone()
        cursor.close()
        self.assertEqual(row["test"], new_test)
        self.assertEqual(row["metadata"], '{"coverage": 100}')

    def test_edit_test_in_db(self):
        new_test = "def test_edit_test_in_db(self): pass"
        self.db_manager.edit_test_in_db(1, new_test)
        cursor = self.db_manager.conn.cursor()
        cursor.execute("SELECT test, history FROM tests WHERE id=?", (1,))
        row = cursor.fetchone()
        cursor.close()
        self.assertEqual(row["test"], new_test)
        self.assertEqual(json.loads(row["history"])[-1]["content"], new_test)

    def test_update_token_count(self):
        self.db_manager.update_token_count("gpt-3.5-turbo", 50, 100)
        cursor = self.db_manager.conn.cursor()
        cursor.execute(
            "SELECT input_tokens, output_tokens FROM token_usage WHERE model=?",
            ("gpt-3.5-turbo",)
        )
        row = cursor.fetchone()
        cursor.close()
        self.assertEqual(row["input_tokens"], 150)
        self.assertEqual(row["output_tokens"], 300)

    def test_delete_row_from_db(self):
        cursor = self.db_manager.conn.cursor()
        self.db_manager.delete_row_from_db(1)
        cursor.execute("SELECT * FROM tests")
        result = cursor.fetchone()
        self.assertIsNone(result)
