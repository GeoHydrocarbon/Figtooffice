from dataclasses import dataclass


@dataclass
class WordRecognitionOptions:
    preserve_markdown: bool = False
