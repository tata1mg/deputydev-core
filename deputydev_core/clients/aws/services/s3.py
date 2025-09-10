from typing import Any, ClassVar, Dict, Optional

from types_aiobotocore_s3.client import S3Client

from deputydev_core.clients.aws.aws_client_manager import AWSClientManager

# from deputydev_core.llm_handler.service_clients.aws.dataclasses.aws_client_manager import AWSConnectionParams  # noqa: ERA001


class AWSS3ServiceClient:
    _client_managers: ClassVar[Dict[str, AWSClientManager]] = {}

    # constructor
    def __init__(self, bucket_name: str, region_name: str) -> None:
        self.region_name = region_name
        self.bucket_name = bucket_name
        self.aws_service_name = "s3"

        client_key = f"{self.bucket_name}_{self.region_name}"

        # Check if we already have a client manager for this configuration
        if client_key not in self._client_managers:
            self._client_managers[client_key] = AWSClientManager(
                aws_service_name=self.aws_service_name,
                region_name=self.region_name,
                # aws_connection_params=AWSConnectionParams(  # noqa: ERA001
                #     aws_access_key_id="test",  # noqa: ERA001
                #     aws_secret_access_key="test",  # noqa: ERA001
                #     endpoint_url="http://localhost:4566",  # LocalStack endpoint for testing  # noqa: ERA001
                # ),
            )

        # Use the shared client manager
        self.aws_client_manager = self._client_managers[client_key]

    async def create_presigned_post_url(
        self, object_name: str, content_type: str, expiry: int, s3_key: str, min_bytes: int, max_bytes: int
    ) -> Dict[str, Any]:
        """
        Generate a presigned URL to share an S3 object
        """
        s3_client: S3Client = await self.aws_client_manager.get_client()  # type: ignore
        fields = {"Content-Type": content_type, "acl": "private", "key": s3_key}
        response = await s3_client.generate_presigned_post(
            Bucket=self.bucket_name,
            Key=s3_key,
            Fields=fields,
            Conditions=[
                {"Content-Type": content_type},
                ["content-length-range", min_bytes, max_bytes],
                {"acl": "private"},
                ["starts-with", "$key", s3_key],
            ],
            ExpiresIn=expiry,
        )
        return response

    async def create_presigned_get_url(self, s3_key: str, expiry: int) -> str:
        """
        Generate a presigned URL to share an S3 object
        """
        s3_client: S3Client = await self.aws_client_manager.get_client()  # type: ignore
        response = await s3_client.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": self.bucket_name, "Key": s3_key},
            ExpiresIn=expiry,
        )
        return response

    async def get_object(self, object_name: str) -> bytes:
        s3_client: S3Client = await self.aws_client_manager.get_client()  # type: ignore
        response = await s3_client.get_object(Bucket=self.bucket_name, Key=object_name)
        async with response["Body"] as stream:  # type: ignore
            return await stream.read()  # type: ignore

    async def delete_object(self, object_name: str) -> None:
        """
        Delete an object from S3
        """
        s3_client: S3Client = await self.aws_client_manager.get_client()  # type: ignore
        await s3_client.delete_object(Bucket=self.bucket_name, Key=object_name)

    async def create_presigned_put_url(
        self,
        s3_key: str,
        expiry: int,
        cache_control: Optional[str] = None,
    ) -> str:
        """
        Generate a presigned URL to upload binary with optional Cache-Control header.
        """
        s3_client: S3Client = await self.aws_client_manager.get_client()  # type: ignore
        params = {
            "Bucket": self.bucket_name,
            "Key": s3_key,
        }
        if cache_control:
            params["CacheControl"] = cache_control
        response = await s3_client.generate_presigned_url(ClientMethod="put_object", Params=params, ExpiresIn=expiry)
        return response
