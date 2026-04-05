import os
import logging
from typing import Dict, List, Callable, Tuple, Any, Optional

logger = logging.getLogger(__name__)

class TaskDependencyManager:
    """
    Manages task dependencies and ensures tasks are executed in the correct order.
    Each task produces one or more output files that may be required by subsequent tasks.
    The manager tracks these dependencies and ensures all prerequisites are met before
    executing a task.
    """
    
    def __init__(self, base_dir: str):
        """
        Initialize the task manager with a base directory for the current job/video.
        
        Args:
            base_dir: Base directory for the current processing job
        """
        self.base_dir = base_dir
        self.tasks = []
        self.product_to_task = {}
        self.completed_tasks = set()
    
    def add_task(self, output_files: List[str], func: Callable[[str], Any], 
                 description: str, dependencies: List[str] = None) -> int:
        """
        Add a new task to the dependency graph.
        
        Args:
            output_files: List of output files this task produces
            func: Function to execute for this task (takes base_dir as argument)
            description: Human-readable description of the task
            dependencies: List of files required by this task
            
        Returns:
            Task ID (index in the task list)
        """
        if dependencies is None:
            dependencies = []
            
        task_id = len(self.tasks)
        self.tasks.append((output_files, func, description, dependencies))
        
        # Register each output file with its producing task
        for output_file in output_files:
            self.product_to_task[output_file] = task_id
            
        return task_id
    
    def any_exist(self, paths: List[str]) -> bool:
        """
        Check if any of the given paths exist.
        
        Args:
            paths: List of file paths to check
            
        Returns:
            True if any of the paths exist, False otherwise
        """
        return any(os.path.exists(p) for p in paths)
    
    def ensure_task(self, task_id: int) -> bool:
        """
        Ensure a task is completed by checking if its output files exist,
        and if not, executing the task after ensuring all dependencies are met.
        
        Args:
            task_id: ID of the task to ensure
            
        Returns:
            True if the task was completed successfully, False otherwise
        """
        # If already completed, return immediately
        if task_id in self.completed_tasks:
            return True
            
        output_files, func, description, dependencies = self.tasks[task_id]
        
        # If all output files exist, mark as completed and return
        if all(os.path.exists(out_file) for out_file in output_files):
            self.completed_tasks.add(task_id)
            logger.info(f"Task {task_id} ({description}) already completed.")
            return True
        
        # First ensure all dependencies exist
        for dep in dependencies:
            # If dependency doesn't exist, find the task that produces it
            if not os.path.exists(dep):
                if dep in self.product_to_task:
                    # Recursively ensure the dependency-producing task
                    dep_task_id = self.product_to_task[dep]
                    if not self.ensure_task(dep_task_id):
                        logger.warning(f"Failed to ensure dependency {dep} for task {task_id}")
                        return False
                else:
                    # For multi-dependencies, only need one to exist
                    if isinstance(dependencies, list) and self.any_exist(dependencies):
                        break
                    logger.warning(f"Missing dependency {dep} for task {task_id} and no task produces it.")
                    return False
        
        # Execute the task now that dependencies are met
        logger.info(f"Executing task {task_id}: {description}")
        try:
            func(self.base_dir)
            
            # Verify that output files were created
            if not all(os.path.exists(out_file) for out_file in output_files):
                logger.error(f"Task {task_id} did not produce all expected output files")
                return False
                
            self.completed_tasks.add(task_id)
            logger.info(f"Task {task_id} completed successfully.")
            return True
        except Exception as e:
            logger.error(f"Task {task_id} failed with error: {str(e)}")
            return False
    
    def run_all_tasks(self) -> bool:
        """
        Run all tasks in the dependency graph, ensuring dependencies are met.
        
        Returns:
            True if all tasks completed successfully, False otherwise
        """
        success = True
        for task_id in range(len(self.tasks)):
            if not self.ensure_task(task_id):
                success = False
                # Continue with other tasks even if one fails
                
        return success
    
    def get_output_files(self) -> Dict[str, List[str]]:
        """
        Get all output files organized by category.
        This is useful for packaging results without searching.
        
        Returns:
            Dictionary of file categories to lists of file paths
        """
        result = {
            "subtitles": [],
            "audio": [],
            "translations": [],
            "subtitled_videos": [],
            "output": [],
            "metadata": [],
            "logs": [],
            "other": []
        }
        
        # Collect all output files from completed tasks
        for task_id in self.completed_tasks:
            output_files, _, _, _ = self.tasks[task_id]
            for file_path in output_files:
                if not os.path.exists(file_path):
                    continue
                    
                # Categorize file based on path or extension
                if 'subtitle' in file_path.lower() or file_path.endswith('.srt'):
                    result["subtitles"].append(file_path)
                elif 'audio' in file_path.lower() or file_path.endswith(('.mp3', '.wav')):
                    result["audio"].append(file_path)
                elif 'translation' in file_path.lower():
                    result["translations"].append(file_path)
                elif 'videos' in file_path.lower() and 'subtitle' in file_path.lower():
                    result["subtitled_videos"].append(file_path)
                elif file_path.endswith(('.mp4', '.mov', '.avi')):
                    result["output"].append(file_path)
                elif 'metadata' in file_path.lower() or file_path.endswith('.json'):
                    result["metadata"].append(file_path)
                elif 'log' in file_path.lower() or file_path.endswith('.log'):
                    result["logs"].append(file_path)
                else:
                    result["other"].append(file_path)
                    
        return result
