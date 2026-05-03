from modules.pdf_to_word.service import PdfToWordService


def create_module() -> PdfToWordService:
    return PdfToWordService()
