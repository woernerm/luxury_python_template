from unittest import TestCase
from example_package_your_username_here.example_module import example_function


class MyExampleTestCase(TestCase):
    def test_example_function(self):
        value = 42
        self.assertEqual(example_function(value), value)
