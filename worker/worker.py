"""
Runway Worker - Main polling loop for task processing
"""
import os
import sys
import time
import signal
import threading
import yaml
from pathlib import Path
from typing import Dict, Any

# Add worker directory to path
sys.path.insert(0, str(Path(__file__).parent))

from logger import setup_logger, log_task_start, log_task_complete, log_step, log_error
from api_client import VercelAPIClient
from storage import upload_file, cleanup_file
from runway_client import RunwayClient


class RunwayWorker:
    """Main worker class for polling and processing tasks"""

    def __init__(self, config_path: str = "worker/config.yaml"):
        """Initialize worker"""
        # Load configuration
        self.config = self._load_config(config_path)

        # Setup logger
        self.logger = setup_logger(
            log_dir=self.config["log_dir"],
            worker_id=self.config["worker_id"]
        )

        # Initialize API client
        self.api_client = VercelAPIClient(
            base_url=self.config["vercel_api_url"],
            worker_token=self.config["worker_token"],
            worker_id=self.config["worker_id"],
            worker_type=self.config.get("worker_type", "runway"),
            timeout=self.config["api_timeout"]
        )

        # Initialize Runway client
        self.runway_client = RunwayClient(
            api_key=self.config["runway_api_key"],
            model=self.config.get("runway_model", "gen4_turbo"),
            timeout=self.config.get("runway_timeout", 600)
        )

        # Setup temp directory
        Path(self.config["temp_dir"]).mkdir(parents=True, exist_ok=True)

        # Shutdown flag
        self.shutdown_requested = False

        # Heartbeat control
        self.heartbeat_active = False
        self.heartbeat_interval = self.config.get("heartbeat_interval", 120)

        # Adaptive polling control
        self.last_task_time = None
        self.polling_interval_slow = self.config.get("polling_interval_slow", 60)
        self.polling_interval_fast = self.config.get("polling_interval_fast", 5)
        self.fast_polling_duration = self.config.get("fast_polling_duration", 1800)

        self.logger.info("="*60)
        self.logger.info(f"Worker initialized: {self.config['worker_id']}")
        self.logger.info(f"Next.js API: {self.config['vercel_api_url']}")
        self.logger.info(f"Runway Model: {self.config.get('runway_model', 'gen4_turbo')}")
        self.logger.info(f"Polling: {self.polling_interval_slow}s (slow) / {self.polling_interval_fast}s (fast after task)")
        self.logger.info("="*60)

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        # Replace environment variables
        for key, value in config.items():
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                env_var = value[2:-1]
                config[key] = os.environ.get(env_var, value)

        return config

    def _handle_shutdown(self, signum, frame):
        """Handle shutdown signal"""
        self.logger.info("Shutdown signal received, finishing current task...")
        self.shutdown_requested = True

    def _heartbeat_loop(self, item_id: str):
        """Background heartbeat loop to extend task lease"""
        while self.heartbeat_active:
            time.sleep(self.heartbeat_interval)
            if not self.heartbeat_active:
                break
            try:
                success = self.api_client.heartbeat(item_id, extend_seconds=300)
                if success:
                    self.logger.info(f"[HEARTBEAT] Lease extended for item {item_id}")
            except Exception as e:
                self.logger.warning(f"[HEARTBEAT] Failed: {e}")

    def process_task(self, task: Dict[str, Any]) -> bool:
        """
        Process a single task

        Args:
            task: Task dictionary from API

        Returns:
            True if task completed successfully, False otherwise
        """
        item_id = task["item_id"]
        group_id = task.get("group_id", "unknown")
        photo_storage_path = task["photo_storage_path"]
        prompt = task.get("prompt", "")
        frame_num = task.get("frame_num")
        inference_provider = task.get("inference_provider", "gen4_turbo")

        log_task_start(self.logger, item_id, group_id)

        # Model mapping based on inference_provider
        model_map = {
            "wan_local": None,  # Skip (other worker handles this)
            "gen4_turbo": "gen4_turbo",
            "gen4.5_turbo": "gen4.5_turbo",
            "gen3a_turbo": "gen3a_turbo",
            "veo3": "veo3",
            "veo3.1": "veo3.1",
            "veo3.1_fast": "veo3.1_fast"
        }

        model = model_map.get(inference_provider, "gen4_turbo")

        if model is None:
            # This task is for WAN worker, skip
            self.logger.warning(f"Task {item_id} is for WAN worker, skipping")
            return False

        # Calculate duration from frame_num (24fps)
        if frame_num:
            duration = frame_num / 24.0
            duration = max(2.0, min(10.0, duration))  # Clamp to 2-10 seconds
        else:
            duration = self.config.get("runway_default_duration", 5.0)

        # Define temp file paths (only output needed now)
        temp_output = Path(self.config["temp_dir"]) / f"{item_id}_output.mp4"

        # Start heartbeat thread
        self.heartbeat_active = True
        heartbeat_thread = threading.Thread(target=self._heartbeat_loop, args=(item_id,))
        heartbeat_thread.daemon = True
        heartbeat_thread.start()

        runway_task_id = None

        try:
            # Step 1: Get presigned download URL (direct use for Runway API)
            log_step(self.logger, 1, "Getting image URL...")
            presign_data = self.api_client.get_presigned_download_url(photo_storage_path)
            image_url = presign_data["url"]
            self.logger.info(f"Image URL obtained: {image_url[:80]}...")

            # Step 2: Run Runway I2V generation (using URL directly)
            log_step(self.logger, 2, "Calling Runway API...")
            self.logger.info(f"Prompt: {prompt}")
            self.logger.info(f"Model: {model}")
            self.logger.info(f"Duration: {duration:.2f}s")
            self.logger.info(f"Ratio: {self.config.get('runway_default_ratio', '1280:720')}")

            self.runway_client.generate_video(
                input_image_url=image_url,  # Use presigned URL directly
                output_video_path=str(temp_output),
                prompt=prompt,
                duration=duration,
                ratio=self.config.get("runway_default_ratio", "1280:720"),
                model_override=model
            )
            self.logger.info(f"Generation complete: {temp_output}")

            # Step 3: Get presigned upload URL
            log_step(self.logger, 3, "Getting upload URL...")
            presign_data = self.api_client.get_presigned_upload_url(
                video_item_id=item_id,
                file_extension="mp4"
            )
            upload_url = presign_data["url"]
            video_storage_path = presign_data["storage_path"]

            # Step 4: Upload result
            log_step(self.logger, 4, "Uploading result video...")
            upload_file(str(temp_output), upload_url, "video/mp4")
            self.logger.info(f"Uploaded to: {video_storage_path}")

            # Step 5: Report success
            log_step(self.logger, 5, "Reporting task completion...")
            self.api_client.report_task_result(
                item_id=item_id,
                status="completed",
                video_storage_path=video_storage_path,
                runway_task_id=runway_task_id
            )

            log_task_complete(self.logger, item_id, "SUCCESS")

            # Cleanup temp files
            if self.config.get("auto_cleanup_temp", True):
                cleanup_file(str(temp_output))

            return True

        except Exception as e:
            # Report failure
            log_error(self.logger, f"Task {item_id} failed", e)

            try:
                self.api_client.report_task_result(
                    item_id=item_id,
                    status="failed",
                    error_message=f"Runway: {str(e)}"
                )
            except Exception as report_error:
                log_error(self.logger, "Failed to report task failure", report_error)

            log_task_complete(self.logger, item_id, "FAILED")

            # Cleanup temp files
            cleanup_file(str(temp_output))

            return False

        finally:
            # Stop heartbeat thread
            self.heartbeat_active = False
            heartbeat_thread.join(timeout=1)

    def _get_polling_interval(self) -> int:
        """
        Calculate current polling interval based on last task time

        Returns:
            Polling interval in seconds (fast or slow)
        """
        if self.last_task_time is None:
            return self.polling_interval_slow

        elapsed = time.time() - self.last_task_time
        if elapsed < self.fast_polling_duration:
            return self.polling_interval_fast
        else:
            return self.polling_interval_slow

    def run(self):
        """Main polling loop"""
        # Register signal handlers
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

        self.logger.info("Starting polling loop...")
        self.logger.info("")

        while not self.shutdown_requested:
            try:
                # Calculate current polling interval
                current_interval = self._get_polling_interval()

                # Get next task
                self.logger.info("[POLLING] Requesting next task...")
                task = self.api_client.get_next_task(
                    lease_duration_seconds=self.config.get("lease_duration_seconds", 600)
                )

                if task is None:
                    self.logger.info("[IDLE] No task available")
                    self.logger.info(f"Waiting {current_interval} seconds...")
                    self.logger.info("")
                    time.sleep(current_interval)
                    continue

                # Process task
                self.logger.info(f"[TASK RECEIVED] item_id: {task['item_id']}")
                self.logger.info("")
                success = self.process_task(task)

                # Update last task time after processing
                self.last_task_time = time.time()
                self.logger.info(f"Task completed. Switching to fast polling ({self.polling_interval_fast}s) for {self.fast_polling_duration}s")
                self.logger.info("")

                # Brief pause before next poll
                time.sleep(1)

            except KeyboardInterrupt:
                self.logger.info("KeyboardInterrupt received, shutting down...")
                break

            except Exception as e:
                log_error(self.logger, "Error in main loop", e)
                current_interval = self._get_polling_interval()
                self.logger.info(f"Retrying in {current_interval} seconds...")
                time.sleep(current_interval)

        self.logger.info("Worker shutdown complete")


def main():
    """Entry point"""
    # Get config path from command line or use default
    config_path = sys.argv[1] if len(sys.argv) > 1 else "worker/config.yaml"

    # Create and run worker
    worker = RunwayWorker(config_path)
    worker.run()


if __name__ == "__main__":
    main()
