# Re-export JobResult class and ResultType enum from job.py
from .job import JobResult, ResultType

# Export the types for easier imports
__all__ = ['JobResult', 'ResultType']
