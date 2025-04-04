"""
Qdrant connector module for Fegis.

Provides a client for interacting with the Qdrant vector database
to store and retrieve structured memory entries.
"""

from typing import Optional

from qdrant_client import AsyncQdrantClient


class QdrantConnector:
    """
    Connector for Qdrant vector database operations.

    Handles vector embeddings, search, and CRUD operations for
    structured memory entries.
    """

    def __init__(
            self,
            qdrant_url: str,
            grpc_port: int,
            prefer_grpc: bool,
            qdrant_api_key: Optional[str],
            collection_name: str,
            fastembed_model: str,
    ):
        """Initialize the Qdrant connector with connection details."""
        self._qdrant_url = qdrant_url
        self._grpc_port = grpc_port
        self._prefer_grpc = prefer_grpc
        self._qdrant_api_key = qdrant_api_key
        self._collection_name = collection_name
        self._fastembed_model = fastembed_model

        # Create the client
        self.client = AsyncQdrantClient(
            url=self._qdrant_url,
            grpc_port=self._grpc_port,
            prefer_grpc=self._prefer_grpc,
            api_key=self._qdrant_api_key,
        )

    async def ensure_collection_exists(self) -> bool:
        """
        Ensure the collection exists, creating it if necessary.

        Returns:
            bool: True if collection already existed, False if created
        """
        try:
            collection_exists = await self.client.collection_exists(self._collection_name)

            # Set the embedding model
            self.client.set_model(self._fastembed_model)

            if not collection_exists:
                try:
                    await self.client.create_collection(
                        collection_name=self._collection_name,
                        vectors_config=self.client.get_fastembed_vector_params()
                    )
                    return False
                except Exception as e:
                    # Handle potential race condition
                    if "ALREADY_EXISTS" in str(e) or "already exists" in str(e):
                        return True
                    raise

            return True

        except Exception as e:
            raise
