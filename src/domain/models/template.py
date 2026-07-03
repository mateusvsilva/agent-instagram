from pydantic import BaseModel, Field


class DalleParams(BaseModel):
    size: str = "1024x1792"
    quality: str = "hd"
    style: str = "vivid"


class PromptTemplate(BaseModel):
    id: str
    name: str
    prompt: str
    variables: dict[str, list[str]] = Field(default_factory=dict)
    caption_template: str
    hashtag_pool: list[str] = Field(default_factory=list)
    image_count: int = 4
    dalle_params: DalleParams = Field(default_factory=DalleParams)
    active: bool = True
