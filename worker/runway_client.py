"""
Runway ML API Client for I2V Generation (using official SDK)
"""
import base64
import requests
from pathlib import Path
from typing import Optional
from runwayml import RunwayML


class RunwayClient:
    """Client for Runway ML Gen-4 / Veo 3.1 API (using official SDK)"""

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
        self.client = RunwayML(api_key=api_key)
        self.upload_url = "https://api.dev.runwayml.com/v1/uploads"

    def upload_image(self, image_path: str) -> str:
        """
        Upload image to Runway's ephemeral storage

        Args:
            image_path: Path to local image file

        Returns:
            runway:// URI for the uploaded image

        Raises:
            Exception if upload fails
        """
        if not Path(image_path).exists():
            raise FileNotFoundError(f"Image file not found: {image_path}")

        filename = Path(image_path).name

        try:
            # Step 1: Request upload URL
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "X-Runway-Version": "2024-11-06",
                "Content-Type": "application/json"
            }
            payload = {
                "filename": filename,
                "type": "ephemeral"
            }

            response = requests.post(
                self.upload_url,
                json=payload,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            upload_data = response.json()

            upload_url = upload_data["uploadUrl"]
            fields = upload_data["fields"]
            runway_uri = upload_data["runwayUri"]

            # Step 2: Upload file using multipart form data
            with open(image_path, 'rb') as f:
                files = {'file': (filename, f)}
                upload_response = requests.post(
                    upload_url,
                    data=fields,
                    files=files,
                    timeout=60
                )
                upload_response.raise_for_status()

            return runway_uri

        except Exception as e:
            raise Exception(f"Runway image upload failed: {str(e)}")

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
            input_image_path: Path to local image file
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
        # Validate input file
        if not Path(input_image_path).exists():
            raise FileNotFoundError(f"Input image not found: {input_image_path}")

        # Ensure output directory exists
        Path(output_video_path).parent.mkdir(parents=True, exist_ok=True)

        # Upload image to Runway and get runway:// URI
        runway_uri = self.upload_image(input_image_path)

        # Use model override if provided
        model = model_override or self.model

        # Create I2V task and wait for completion using SDK
        try:
            task = self.client.image_to_video.create(
                model=model,
                prompt_image=runway_uri,  # Use runway:// URI from upload
                prompt_text=prompt,
                duration=int(duration),
                ratio=ratio
            ).wait_for_task_output()

            # Get video URL from task output
            video_url = task.output[0]

            # Download video
            self._download_video(video_url, output_video_path)

            return output_video_path

        except Exception as e:
            raise Exception(f"Runway video generation failed: {str(e)}")

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
