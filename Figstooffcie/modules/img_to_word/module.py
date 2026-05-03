from modules.img_to_word.service import ImageToWordService


def create_module() -> ImageToWordService:
    return ImageToWordService()
