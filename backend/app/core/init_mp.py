"""
Initialize multiprocessing with spawn method before any other imports.
This must be imported at the very beginning of the application.
"""
import os
import multiprocessing

# Set environment variable to prefer spawn
os.environ['PYTHON_MULTIPROCESSING_METHOD'] = 'spawn'

# Set the start method
if multiprocessing.get_start_method(allow_none=True) != 'spawn':
    try:
        multiprocessing.set_start_method('spawn', force=True)
    except RuntimeError as e:
        print(f"Warning: Could not set multiprocessing start method to 'spawn': {e}")

# Verify the start method
current_method = multiprocessing.get_start_method()
print(f"Multiprocessing start method set to: {current_method}")
