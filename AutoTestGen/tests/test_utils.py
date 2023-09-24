import unittest
from unittest.mock import patch
from AutoTestGen.utils import config
from AutoTestGen.utils import ADAPTERS, MODELS

from AutoTestGen.utils import (
    set_adapter,
    set_api_keys,
    set_model,
    count_tokens

)

class TestSetAdapter(unittest.TestCase):

    def test_set_adapter_valid_language(self):
        set_adapter('python', '/AutoTestGen/db_manager.py')
        self.assertIsInstance(config.ADAPTER, ADAPTERS["python"])

    def test_set_adapter_invalid_language(self):
        with self.assertRaises(ValueError):
            set_adapter('unsupported_language', '/AutoTestGen/db_manager.py')

    def test_set_adapter_empty_module_dir(self):
        with self.assertRaises(Exception):
            set_adapter('python', '')

class TestSetApiKeys(unittest.TestCase):

    @patch('AutoTestGen.utils.config')
    def test_set_api_keys(self, mock_config):
        api_key = 'test_api_key'
        org_key = 'test_org_key'
        set_api_keys(api_key, org_key)
        self.assertEqual(mock_config.API_KEY, api_key)
        self.assertEqual(mock_config.ORG_KEY, org_key)

    @patch('AutoTestGen.utils.config')
    def test_set_api_keys_empty(self, mock_config):
        api_key = None
        org_key = None
        set_api_keys(api_key, org_key)
        self.assertEqual(mock_config.API_KEY, api_key)
        self.assertEqual(mock_config.ORG_KEY, org_key)

class TestSetModel(unittest.TestCase):
    def setUp(self):
        self.original_model = config.MODEL

    def tearDown(self):
        config.MODEL = self.original_model

    def test_set_model_with_valid_model(self):
        for model in MODELS:
            set_model(model)
            self.assertEqual(config.MODEL, model)

    def test_set_model_with_invalid_model(self):
        with self.assertRaises(ValueError):
            set_model("invalid_model")

class TestCountTokens(unittest.TestCase):

    @patch('AutoTestGen.utils.config')
    @patch('AutoTestGen.utils.tiktoken')
    def test_count_tokens(self, mock_tiktoken, mock_config):
        mock_tiktoken.encoding_for_model.return_value.encode.side_effect = (
            lambda x: list(x)
        )
        messages = [{"content": "Hello"}, {"content": "World"}]
        result = count_tokens(messages)
        self.assertEqual(result, 10)
        mock_tiktoken.encoding_for_model.assert_called_once_with(
            mock_config.MODEL
        )
        mock_tiktoken.encoding_for_model.return_value.encode.assert_any_call(
            "Hello"
        )
        mock_tiktoken.encoding_for_model.return_value.encode.assert_any_call(
            "World"
        )

    @patch('AutoTestGen.utils.config')
    @patch('AutoTestGen.utils.tiktoken')
    def test_count_tokens_empty(self, mock_tiktoken, mock_config):
        mock_tiktoken.encoding_for_model.return_value.encode.side_effect = (
            lambda x: list(x)
        )
        messages = []
        result = count_tokens(messages)
        self.assertEqual(result, 0)
        mock_tiktoken.encoding_for_model.assert_called_once_with(
            mock_config.MODEL
        )

    @patch('AutoTestGen.utils.config')
    @patch('AutoTestGen.utils.tiktoken')
    def test_count_tokens_no_content(self, mock_tiktoken, mock_config):
        mock_tiktoken.encoding_for_model.return_value.encode.side_effect = (
            lambda x: list(x)
        )
        messages = [{"no_content": "Hello"}, {"no_content": "World"}]
        with self.assertRaises(KeyError):
            count_tokens(messages)
        mock_tiktoken.encoding_for_model.assert_called_once_with(
            mock_config.MODEL
        )
