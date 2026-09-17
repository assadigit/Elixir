"""
Token-based segmenter – splits document into fixed-size chunks by token count.
Used as the ultimate fallback when no structural headings or semantic info is available.
"""


from core.models import ConversionRequest, Segment
from utils.logging import get_main_logger
from utils.token_counter import count_tokens

logger = get_main_logger()


class TokenSegmenter:
    """
    Splits the document into segments each not exceeding a token limit.
    Respects paragraph boundaries (splits at double newlines when possible).
    """

    def __init__(self, request: ConversionRequest):
        self.request = request
        self.token_limit = request.token_limit_per_segment

    def segment(
        self,
        markdown_text: str,
        total_pages: int,
        page_markers: list[tuple[int, int]],
    ) -> list[Segment]:
        logger.info(f"[TokenSegmenter] Splitting — limit: {self.token_limit} tokens/segment")

        paragraphs = markdown_text.split('\n\n')
        segments: list[Segment] = []
        current_content: list[str] = []
        current_tokens = 0
        chunk_num = 1

        def get_page_for_offset(offset: int) -> int:
            for p_num, pos in reversed(page_markers):
                if offset >= pos:
                    return p_num
            return 1

        text_pointer = 0

        for para in paragraphs:
            para_tokens = count_tokens(para)

            if current_tokens + para_tokens > self.token_limit and current_content:
                start_page = get_page_for_offset(
                    text_pointer - len('\n\n'.join(current_content))
                )
                end_page = get_page_for_offset(text_pointer)
                segments.append(
                    Segment(
                        heading=f"Chunk {chunk_num}",
                        content='\n\n'.join(current_content).strip(),
                        start_page=max(1, start_page),
                        end_page=max(1, end_page),
                        segment_type="chunk",
                    )
                )
                chunk_num += 1
                current_content = [para]
                current_tokens = para_tokens
            else:
                current_content.append(para)
                current_tokens += para_tokens

            text_pointer += len(para) + 2  # +2 for \n\n

        if current_content:
            start_page = get_page_for_offset(
                text_pointer - len('\n\n'.join(current_content))
            )
            segments.append(
                Segment(
                    heading=f"Chunk {chunk_num}",
                    content='\n\n'.join(current_content).strip(),
                    start_page=max(1, start_page),
                    end_page=total_pages,
                    segment_type="chunk",
                )
            )

        logger.info(f"[TokenSegmenter] Created {len(segments)} chunks.")
        return segments
