"""Custom S3 storage backend for Supabase that avoids HeadObject calls."""

from storages.backends.s3boto3 import S3Boto3Storage


class SupabaseS3Storage(S3Boto3Storage):
    """S3 storage backend for Supabase that avoids HeadObject calls on exists()."""
    def exists(self, name):
        return False