from unittest import TestCase as _TestCase
import src.pythontemplate.example_module as _example


class MyExampleTestCase(_TestCase):
    def test_example_function(self):
        value = 42
        self.assertEqual(_example.example_function(value), value)
