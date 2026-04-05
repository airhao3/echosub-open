#!/usr/bin/env python
import os
import click
import subprocess
import signal
import sys
import json
from pathlib import Path
from datetime import datetime

# Base directory
BASE_DIR = Path(__file__).parent.absolute()

@click.group()
def cli():
    """Management script for VideoLingo SaaS backend."""
    pass

@cli.command()
@click.option('--host', '-h', default='0.0.0.0', help='Host to bind')
@click.option('--port', '-p', default=8000, help='Port to bind')
@click.option('--reload/--no-reload', default=True, help='Enable/disable auto-reload')
def runserver(host, port, reload):
    """Run the FastAPI development server."""
    click.echo(f"Starting development server at {host}:{port}")
    cmd = ["uvicorn", "app.main:app", "--host", host, "--port", str(port)]
    if reload:
        cmd.append("--reload")
    subprocess.run(cmd)

@cli.command()
@click.option('--loglevel', '-l', default='info', help='Log level')
@click.option('--concurrency', '-c', default=1, help='Worker concurrency')
def worker(loglevel, concurrency):
    """Run the Celery worker."""
    click.echo(f"Starting Celery worker with loglevel={loglevel}, concurrency={concurrency}")
    cmd = [
        "celery", "-A", "celery_worker.celery_app", "worker", 
        "--loglevel", loglevel,
        "--concurrency", str(concurrency),
    ]
    subprocess.run(cmd)

@cli.command()
@click.option('--host', '-h', default='0.0.0.0', help='Host to bind')
@click.option('--port', '-p', default=5555, help='Port to bind')
def flower(host, port):
    """Run Celery Flower monitoring tool."""
    click.echo(f"Starting Celery Flower at {host}:{port}")
    cmd = [
        "celery", "-A", "celery_worker.celery_app", "flower", 
        "--address", host,
        "--port", str(port),
    ]
    subprocess.run(cmd)

@cli.command()
def initdb():
    """Initialize database tables."""
    click.echo("Creating database tables...")
    cmd = ["alembic", "upgrade", "head"]
    subprocess.run(cmd)

@cli.command()
@click.option('--message', '-m', required=True, help='Migration message')
def makemigrations(message):
    """Generate database migration."""
    click.echo(f"Creating migration with message: {message}")
    cmd = ["alembic", "revision", "--autogenerate", "-m", message]
    subprocess.run(cmd)

@cli.command()
def runall():
    """Run both the web server and worker in one command (for development)."""
    click.echo("Starting both web server and Celery worker...")
    
    # Create necessary directories
    os.makedirs(os.path.join(BASE_DIR, "logs"), exist_ok=True)
    
    # Start celery worker
    worker_cmd = ["celery", "-A", "celery_worker.celery_app", "worker", "--loglevel=info", "--reload"]
    worker_process = subprocess.Popen(
        worker_cmd, 
        stdout=open(os.path.join(BASE_DIR, "logs", "celery_worker.log"), "a"),
        stderr=subprocess.STDOUT
    )
    
    # Start uvicorn server
    server_cmd = ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
    server_process = subprocess.Popen(
        server_cmd,
        stdout=open(os.path.join(BASE_DIR, "logs", "uvicorn.log"), "a"),
        stderr=subprocess.STDOUT
    )
    
    click.echo("Both processes started. Press Ctrl+C to quit.")
    
    try:
        # Wait for user to press Ctrl+C
        signal.pause()
    except (KeyboardInterrupt, SystemExit):
        click.echo("Shutting down...")
    finally:
        # Terminate both processes
        worker_process.terminate()
        server_process.terminate()
        worker_process.wait()
        server_process.wait()
        click.echo("All processes terminated.")

@cli.command()
@click.option('--content-hash', help='Content hash of the video to check')
@click.option('--language', help='Language of the processed video')
@click.option('--list-all', is_flag=True, help='List all processing records')
@click.option('--clear-record', is_flag=True, help='Clear a specific processing record')
def videorecords(content_hash, language, list_all, clear_record):
    """Manage video processing records."""
    # Import here to avoid circular imports
    from app.core.database import SessionLocal
    from app.models.video_processing_record import VideoProcessingRecord
    
    db = SessionLocal()
    try:
        if list_all:
            click.echo("Listing all video processing records:")
            records = db.query(VideoProcessingRecord).all()
            if not records:
                click.echo("No video processing records found.")
            else:
                # Format output as a table
                click.echo(f"{'ID':<5} {'Content Hash':<15} {'Language':<10} {'Process Type':<15} {'Count':<6} {'Last Processed':<20} {'Path'}")
                click.echo("-" * 80)
                for record in records:
                    last_processed = record.last_processed_at.strftime('%Y-%m-%d %H:%M:%S') if record.last_processed_at else 'N/A'
                    result_path = record.result_path if record.result_path else 'N/A'
                    click.echo(f"{record.id:<5} {record.content_hash[:12]:<15} {record.language:<10} {record.process_type:<15} {record.process_count:<6} {last_processed:<20} {result_path}")
        
        elif content_hash:
            query = db.query(VideoProcessingRecord).filter(VideoProcessingRecord.content_hash == content_hash)
            if language:
                query = query.filter(VideoProcessingRecord.language == language)
                
            records = query.all()
            
            if not records:
                click.echo(f"No processing records found for content hash: {content_hash}")
            else:
                click.echo(f"Found {len(records)} processing records for content hash: {content_hash}")
                for record in records:
                    click.echo(f"\nRecord ID: {record.id}")
                    click.echo(f"Content Hash: {record.content_hash}")
                    click.echo(f"Original Filename: {record.original_filename}")
                    click.echo(f"Language: {record.language}")
                    click.echo(f"Process Type: {record.process_type}")
                    click.echo(f"Process Count: {record.process_count}")
                    click.echo(f"First Processed: {record.first_processed_at}")
                    click.echo(f"Last Processed: {record.last_processed_at}")
                    click.echo(f"Related Job IDs: {record.job_ids}")
                    click.echo(f"Result Path: {record.result_path}")
                    click.echo(f"Is Currently Processing: {record.is_processing}")
                    
                    # Check if the result file exists
                    if record.result_path and os.path.exists(record.result_path):
                        size_mb = os.path.getsize(record.result_path) / (1024 * 1024)
                        click.echo(f"File exists: Yes (Size: {size_mb:.2f} MB)")
                    elif record.result_path:
                        click.echo("File exists: No (Path is set but file not found)")
                    else:
                        click.echo("File exists: No (No path set)")
                    
                    if clear_record:
                        if click.confirm(f"Do you want to delete record {record.id}?"):
                            db.delete(record)
                            db.commit()
                            click.echo(f"Record {record.id} deleted.")
        
        else:
            click.echo("Please specify --content-hash or --list-all")
            
    finally:
        db.close()


@cli.command()
@click.argument('job_id', type=int)
@click.option('--force', is_flag=True, help='Force reprocessing even if video has been processed before')
def reprocess(job_id, force):
    """Reprocess a specific job."""
    # Import here to avoid circular imports
    from app.core.database import SessionLocal
    from app.models.job import Job, JobStatus
    from app.services.workflow_service import WorkflowService
    
    db = SessionLocal()
    try:
        # Find the job
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            click.echo(f"Job {job_id} not found.")
            return
            
        click.echo(f"Found job: {job.title} (Status: {job.status})")
        
        if job.status == JobStatus.PROCESSING:
            click.echo("Cannot reprocess a job that is currently processing.")
            return
            
        # Confirm reprocessing
        if not force and not click.confirm(f"Do you want to reprocess job {job_id}?"):
            click.echo("Reprocessing cancelled.")
            return
            
        # Reset job status for reprocessing
        job.status = JobStatus.PENDING
        job.progress = 0
        job.error_message = None
        db.commit()
        
        click.echo(f"Job {job_id} has been reset to PENDING status. It will be picked up by the worker.")
        
    finally:
        db.close()


if __name__ == '__main__':
    cli()
