
ERROR_MESSAGES = {
    "file_too_large": "The uploaded file exceeds the allowed size limit.",
    "image_too_large_pixels": "The image dimensions exceed the allowed pixel limit.",
    "empty_file": "The uploaded file is empty.",
    "invalid_image": "The uploaded file is not a valid supported image.",
    "unsupported_format": "This image format is not supported.",
    "file_missing": "The stored image file could not be found.",
    "decode_failed": "The stored image could not be decoded.",
    "analysis_error": "Image analysis could not be completed.",
    "timeout": "Image processing timed out.",
    "worker_lost": "The processing worker stopped unexpectedly.",
}


class UploadRejected(Exception):
    def __init__(self, code: str, http_status: int):
        self.code = code
        self.http_status = http_status
        self.message = ERROR_MESSAGES.get(
            code,
            "The uploaded file was rejected.",
        )
        super().__init__(self.message)


class PermanentProcessingError(Exception):
    def __init__(self, code: str):
        self.code = code
        self.message = ERROR_MESSAGES.get(
            code,
            ERROR_MESSAGES["analysis_error"],
        )
        super().__init__(self.message)
