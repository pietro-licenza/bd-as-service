"""
Google Cloud Storage client for uploading generated images.
"""
import os
import json
from datetime import datetime
from typing import List
from google.cloud import storage
from google.cloud import secretmanager


class StorageClient:
    """Client for Google Cloud Storage operations."""
    
    def __init__(self):
        """Initialize GCS client with service account credentials."""
        from app.core.config import settings
        
        self.project_id = settings.GCP_PROJECT_ID
        self.bucket_name = settings.GCP_STORAGE_BUCKET
        self.use_secret_manager = settings.GCP_USE_SECRET_MANAGER
        
        # Debug log
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"StorageClient init: use_secret_manager={self.use_secret_manager}, GCP_USE_SECRET_MANAGER env={os.getenv('GCP_USE_SECRET_MANAGER')}")
        
        # Authenticate
        if self.use_secret_manager:
            # Use credentials injected as environment variable
            credentials_json_str = os.getenv("GCP_SERVICE_ACCOUNT_JSON")
            if credentials_json_str:
                credentials_json = json.loads(credentials_json_str)
            else:
                # Fallback to Secret Manager
                credentials_json = self._get_credentials_from_secret_manager(
                    settings.GCP_SERVICE_ACCOUNT_SECRET_NAME
                )
        else:
            # Prefer GCP_SERVICE_ACCOUNT_JSON from .env if available
            credentials_json_str = os.getenv("GCP_SERVICE_ACCOUNT_JSON") or getattr(settings, "GCP_SERVICE_ACCOUNT_JSON", None)
            if credentials_json_str:
                credentials_json = json.loads(credentials_json_str)
            else:
                key_path_or_json = settings.GCP_SERVICE_ACCOUNT_KEY_PATH
                # If looks like a JSON string, try to parse; otherwise, treat as file path
                if key_path_or_json.strip().startswith('{'):
                    credentials_json = json.loads(key_path_or_json)
                else:
                    credentials_path = os.path.join(
                        os.path.dirname(__file__), 
                        '../../', 
                        key_path_or_json
                    )
                    with open(credentials_path, 'r') as f:
                        credentials_json = json.load(f)
        
        # Initialize storage client
        self.storage_client = storage.Client.from_service_account_info(credentials_json)
        self.bucket = self.storage_client.bucket(self.bucket_name)
    
    def _get_credentials_from_secret_manager(self, secret_name: str) -> dict:
        """Retrieve service account credentials from Secret Manager."""
        client = secretmanager.SecretManagerServiceClient()
        secret_path = f"projects/{self.project_id}/secrets/{secret_name}/versions/latest"
        
        response = client.access_secret_version(request={"name": secret_path})
        credentials_json = json.loads(response.payload.data.decode("UTF-8"))
        
        return credentials_json
    
    def upload_image(self, local_path: str, destination_blob_name: str) -> str:
        """
        Upload image to GCS and return public URL.
        
        Args:
            local_path: Local file path
            destination_blob_name: Path in bucket (e.g., "products/product_1.png")
            
        Returns:
            Public URL of uploaded image
        """
        blob = self.bucket.blob(destination_blob_name)
        blob.upload_from_filename(local_path)
        
        # Make blob publicly accessible
        blob.make_public()
        
        # Return public URL
        return blob.public_url
    
    def upload_images_batch(self, local_paths: List[str], product_name: str, product_id: int = None) -> List[str]:
        """
        Upload multiple images and return list of public URLs.
        
        Args:
            local_paths: List of local file paths
            product_name: Product name for organizing in bucket
            product_id: Optional product ID for better organization
            
        Returns:
            List of public URLs
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        public_urls = []
        
        # Create folder name: "produto_1_Nome_do_Produto" or just "Nome_do_Produto"
        if product_id is not None:
            folder_name = f"produto_{product_id}_{product_name.replace(' ', '_')}"
        else:
            folder_name = product_name.replace(' ', '_')
        
        for idx, local_path in enumerate(local_paths):
            # Create organized path in bucket
            file_extension = os.path.splitext(local_path)[1]
            destination_blob_name = (
                f"products/{folder_name}/{timestamp}_angle_{idx}{file_extension}"
            )
            
            url = self.upload_image(local_path, destination_blob_name)
            public_urls.append(url)
        
        return public_urls


# Singleton instance
_storage_client = None


def get_storage_client() -> StorageClient:
    """Get or create StorageClient singleton instance."""
    global _storage_client
    if _storage_client is None:
        _storage_client = StorageClient()
    return _storage_client
