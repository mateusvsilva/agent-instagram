from pydantic import BaseModel


class BrandIdentity(BaseModel):
    identity: str = ""
    image_guidelines: str = ""
    caption_guidelines: str = ""
    hashtag_strategy: str = ""

    def image_brief(self) -> str:
        return self._join(self.identity, self.image_guidelines)

    def caption_brief(self) -> str:
        return self._join(self.identity, self.caption_guidelines, self.hashtag_strategy)

    @staticmethod
    def _join(*blocks: str) -> str:
        return "\n\n".join(block.strip() for block in blocks if block and block.strip())
