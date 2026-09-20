#!/usr/bin/env python3
"""Unified test runner for NikitaBot test suites."""
import os
import sys
import unittest

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Discover tests in root and tests/
    suite.addTests(loader.discover(".", pattern="test_*.py"))
    suite.addTests(loader.discover("tests", pattern="test_*.py"))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
