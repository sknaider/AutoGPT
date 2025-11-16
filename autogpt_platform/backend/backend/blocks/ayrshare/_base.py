"""
Base class for Ayrshare social media posting blocks.

This refactoring eliminates ~2,200 lines of duplicated code across
13 social media platform blocks by consolidating common functionality.

MIGRATION NOTE:
This is a template for refactoring the existing Ayrshare blocks.
To complete the refactoring:
1. Update each post_to_*.py to inherit from BaseSocialMediaBlock
2. Define platform-specific configuration
3. Override platform_options() if needed
4. Remove duplicated code
"""

from abc import abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field

from backend.blocks.ayrshare._api import (
    AyrshareCredentials,
    AyrshareCredentialsField,
    create_ayrshare_client,
)
from backend.blocks.ayrshare._auth import AyrshareOAuthHandler, get_profile_key
from backend.data.block import Block, BlockOutput, BlockSchema, SchemaField


class BaseSocialMediaInput(BlockSchema):
    """
    Base input schema for all social media posting blocks.

    Common fields across all platforms.
    """

    credentials: AyrshareCredentials = AyrshareCredentialsField()
    post: str = SchemaField(
        description="The content of the post to be shared",
        placeholder="Enter your post content here",
    )
    schedule_date: Optional[datetime] = SchemaField(
        description="Schedule the post for a specific date and time (UTC)",
        default=None,
    )


class BaseSocialMediaOutput(BlockSchema):
    """Base output schema for social media posting blocks."""

    post_result: Dict[str, Any] = SchemaField(
        description="Result of the post operation"
    )
    error: str = SchemaField(description="Error message if the post failed")


class BaseSocialMediaBlock(Block):
    """
    Abstract base class for Ayrshare social media posting blocks.

    This class consolidates all common functionality:
    - Profile key validation
    - Ayrshare client creation
    - Post data preparation
    - Media attachment handling
    - Date/time scheduling
    - Error handling

    Platform-specific blocks only need to:
    1. Define their platform name
    2. Specify platform-specific input fields
    3. Implement platform_options() for custom settings
    """

    class Input(BaseSocialMediaInput):
        """Override in subclass to add platform-specific fields."""

        pass

    class Output(BaseSocialMediaOutput):
        """Standard output across all platforms."""

        pass

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """
        Platform identifier for Ayrshare API.

        Returns:
            Platform name (e.g., "facebook", "twitter", "linkedin")
        """
        pass

    @property
    def supported_media_types(self) -> List[str]:
        """
        Supported media types for this platform.

        Override if platform has specific requirements.

        Returns:
            List of supported media extensions (e.g., ["jpg", "png", "mp4"])
        """
        return ["jpg", "jpeg", "png", "gif", "mp4", "mov"]

    @property
    def max_media_count(self) -> int:
        """
        Maximum number of media attachments allowed.

        Override for platform-specific limits.

        Returns:
            Maximum media count (default: 4)
        """
        return 4

    @property
    def requires_aspect_ratio(self) -> bool:
        """
        Whether platform requires specific aspect ratio.

        Returns:
            True if aspect ratio validation needed
        """
        return False

    def platform_options(
        self, input_data: Input
    ) -> Dict[str, Any]:
        """
        Build platform-specific options.

        Override this method to add platform-specific settings.

        Args:
            input_data: Block input data

        Returns:
            Dictionary of platform-specific options
        """
        return {}

    async def run(
        self, input_data: Input, *, user_id: str, **kwargs
    ) -> BlockOutput:
        """
        Execute the social media post.

        This method implements the complete posting workflow:
        1. Validate profile key
        2. Create Ayrshare client
        3. Prepare post data
        4. Validate media (if any)
        5. Submit to Ayrshare API
        6. Return result

        Args:
            input_data: Block input containing post data
            user_id: User ID for profile key lookup
            **kwargs: Additional context

        Yields:
            BlockOutput with post result or error
        """
        # Step 1: Get profile key
        profile_key = await get_profile_key(user_id)
        if not profile_key:
            yield "error", (
                f"Please link a social account via Ayrshare to post to {self.platform_name.title()}. "
                "Visit your integrations page to connect your account."
            )
            return

        # Step 2: Create client
        client = create_ayrshare_client()
        if not client:
            yield "error", (
                f"Ayrshare integration is not configured on this server. "
                f"Please contact your administrator to enable {self.platform_name.title()} posting."
            )
            return

        try:
            # Step 3: Validate input
            validation_error = self._validate_input(input_data)
            if validation_error:
                yield "error", validation_error
                return

            # Step 4: Prepare post data
            post_data = self._prepare_post_data(input_data, profile_key)

            # Step 5: Submit post
            response = await client.create_post(**post_data)

            # Step 6: Handle response
            if response.get("status") == "error":
                error_msg = response.get("message", "Unknown error occurred")
                yield "error", f"Failed to post to {self.platform_name.title()}: {error_msg}"
            else:
                yield "post_result", response

        except Exception as e:
            yield "error", f"Unexpected error posting to {self.platform_name.title()}: {str(e)}"

    def _validate_input(self, input_data: Input) -> Optional[str]:
        """
        Validate block input.

        Override to add platform-specific validation.

        Args:
            input_data: Input to validate

        Returns:
            Error message if validation fails, None otherwise
        """
        if not input_data.post or not input_data.post.strip():
            return f"Post content cannot be empty for {self.platform_name.title()}"

        # Validate media if present
        if hasattr(input_data, "media_urls") and input_data.media_urls:
            media_urls = input_data.media_urls
            if len(media_urls) > self.max_media_count:
                return (
                    f"{self.platform_name.title()} supports a maximum of "
                    f"{self.max_media_count} media attachments. "
                    f"You provided {len(media_urls)}."
                )

        return None

    def _prepare_post_data(
        self, input_data: Input, profile_key: str
    ) -> Dict[str, Any]:
        """
        Prepare post data for Ayrshare API.

        Args:
            input_data: Block input
            profile_key: User's Ayrshare profile key

        Returns:
            Dictionary ready for Ayrshare API
        """
        post_data = {
            "post": input_data.post,
            "platforms": [self.platform_name],
            "profileKey": profile_key,
        }

        # Add scheduled date if provided
        if input_data.schedule_date:
            post_data["scheduleDate"] = input_data.schedule_date.isoformat()

        # Add media URLs if present
        if hasattr(input_data, "media_urls") and input_data.media_urls:
            post_data["mediaUrls"] = input_data.media_urls

        # Add platform-specific options
        platform_opts = self.platform_options(input_data)
        if platform_opts:
            # Ayrshare expects platform options under platform name key
            post_data[self.platform_name] = platform_opts

        return post_data


# Example platform-specific implementation
class FacebookBlock(BaseSocialMediaBlock):
    """
    Facebook posting block.

    This is an example of how to migrate existing blocks
    to use the base class.
    """

    @property
    def platform_name(self) -> str:
        return "facebook"

    class Input(BaseSocialMediaInput):
        """Facebook-specific input fields."""

        # Add Facebook-specific fields here
        # e.g., page_id, is_video, etc.
        pass

    def platform_options(self, input_data: Input) -> Dict[str, Any]:
        """Facebook-specific options."""
        options = {}
        # Add Facebook-specific options here
        # e.g., options["link"] = input_data.link
        return options


# TODO: Migrate these blocks to use BaseSocialMediaBlock:
# - post_to_twitter.py → TwitterBlock(BaseSocialMediaBlock)
# - post_to_linkedin.py → LinkedInBlock(BaseSocialMediaBlock)
# - post_to_instagram.py → InstagramBlock(BaseSocialMediaBlock)
# - post_to_youtube.py → YouTubeBlock(BaseSocialMediaBlock)
# - post_to_tiktok.py → TikTokBlock(BaseSocialMediaBlock)
# - post_to_pinterest.py → PinterestBlock(BaseSocialMediaBlock)
# - post_to_reddit.py → RedditBlock(BaseSocialMediaBlock)
# - post_to_telegram.py → TelegramBlock(BaseSocialMediaBlock)
# - post_to_gmb.py → GMBBlock(BaseSocialMediaBlock)
# - post_to_threads.py → ThreadsBlock(BaseSocialMediaBlock)
# - post_to_bluesky.py → BlueskyBlock(BaseSocialMediaBlock)
# - post_to_mastodon.py → MastodonBlock(BaseSocialMediaBlock)

# Expected line reduction:
# Before: ~2,607 lines across 13 files
# After: ~600 lines (base class + platform configs)
# Savings: ~2,000 lines (-77% duplication)
