"""
Runway ML API Client for I2V Generation
"""
import os
import time
import base64
import requests
from pathlib import Path
from typing import Optional, Dict, Any


class RunwayClient:
    """Client for Runway ML Gen-4 / Veo 3.1 API"""

    def __init__(self, api_key: str, model: str = "gen4_turbo", timeout: int = 600):
        """
        Initialize Runway client

        Args:
            api_key: Runway API key
            model: Model name ('gen4_turbo', 'gen4.5_turbo', 'gen3a_turbo', 'veo3', 'veo3.1', 'veo3.1_fast')
            timeout: Task completion timeout in seconds
        """
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.base_url = "https://api.runwayml.com/v1"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "X-Runway-Version": "2024-11-06",
            "Content-Type": "application/json"
        }

    def generate_video(
        self,
        input_image_path: str,
        output_video_path: str,
        prompt: str,
        duration: float = 5.0,
        ratio: str = "1280:720",
        model_override: Optional[str] = None
    ) -> str:
        """
        Generate video from image using Runway I2V

        Args:
            input_image_path: Path to input image
            output_video_path: Path where output video will be saved
            prompt: Text prompt for video generation
            duration: Video duration in seconds (2-10)
            ratio: Video ratio (e.g., "1280:720")
            model_override: Override default model

        Returns:
            Path to generated video file

        Raises:
            Exception if generation fails
        """
        # Validate input
        if not Path(input_image_path).exists():
            raise FileNotFoundError(f"Input image not found: {input_image_path}")

        # Ensure output directory exists
        Path(output_video_path).parent.mkdir(parents=True, exist_ok=True)

        # Convert image to data URI
        image_uri = self._image_to_data_uri(input_image_path)

        # Create I2V task
        model = model_override or self.model
        task_id = self._create_i2v_task(
            image_uri=image_uri,
            prompt=prompt,
            duration=duration,
            ratio=ratio,
            model=model
        )

        # Wait for completion
        video_url = self._wait_for_completion(task_id, timeout=self.timeout)

        # Download video
        self._download_video(video_url, output_video_path)

        return output_video_path

    def _image_to_data_uri(self, image_path: str) -> str:
        """
        Convert image file to data URI

        Args:
            image_path: Path to image file

        Returns:
            Data URI string (e.g., "data:image/jpeg;base64,...")
        """
        with open(image_path, 'rb') as f:
            image_data = f.read()

        # Determine MIME type
        ext = Path(image_path).suffix.lower()
        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.webp': 'image/webp'
        }
        mime_type = mime_types.get(ext, 'image/jpeg')

        # Encode to base64
        b64_data = base64.b64encode(image_data).decode('utf-8')

        return f"data:{mime_type};base64,{b64_data}"

    def _create_i2v_task(
        self,
        image_uri: str,
        prompt: str,
        duration: float,
        ratio: str,
        model: str
    ) -> str:
        """
        Create Runway I2V generation task

        Returns:
            Task ID
        """
        url = f"{self.base_url}/image_to_video"
        payload = {
            "model": model,
            "promptImage": image_uri,
            "promptText": prompt,
            "duration": duration,
            "ratio": ratio
        }

        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            return result["id"]

        except requests.exceptions.RequestException as e:
            raise Exception(f"Runway task creation failed: {str(e)}")

    def _wait_for_completion(self, task_id: str, timeout: int, poll_interval: int = 5) -> str:
        """
        Poll task until completion

        Args:
            task_id: Runway task ID
            timeout: Maximum wait time in seconds
            poll_interval: Polling interval in seconds

        Returns:
            Video URL

        Raises:
            Exception if task fails or times out
        """
        start_time = time.time()
        url = f"{self.base_url}/tasks/{task_id}"

        while time.time() - start_time < timeout:
            try:
                response = requests.get(url, headers=self.headers, timeout=30)
                response.raise_for_status()
                result = response.json()

                status = result.get("status")
                elapsed = int(time.time() - start_time)

                if status == "SUCCEEDED":
                    return result["output"][0]  # Video URL
                elif status == "FAILED":
                    failure_reason = result.get("failure", "Unknown error")
                    raise Exception(f"Runway task failed: {failure_reason}")
                elif status in ["PENDING", "RUNNING"]:
                    # Still processing, continue polling
                    time.sleep(poll_interval)
                else:
                    raise Exception(f"Unknown task status: {status}")

            except requests.exceptions.RequestException as e:
                # Retry on network errors
                time.sleep(poll_interval)

        raise TimeoutError(f"Task {task_id} timed out after {timeout}s")

    def _download_video(self, video_url: str, dest_path: str):
        """
        Download video from Runway URL

        Args:
            video_url: Runway video URL
            dest_path: Destination path
        """
        try:
            response = requests.get(video_url, timeout=300, stream=True)
            response.raise_for_status()

            with open(dest_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

        except Exception as e:
            raise Exception(f"Video download failed: {str(e)}")

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get current task status

        Args:
            task_id: Runway task ID

        Returns:
            Task status dict
        """
        url = f"{self.base_url}/tasks/{task_id}"

        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to get task status: {str(e)}")
