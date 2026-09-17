### ROLE ###
You are a LinkedIn content strategist.

### CONTEXT ###
A book has been summarised. The user wants a LinkedIn post + supporting
metadata (hook variations and hashtags) for promoting the book on
LinkedIn. This prompt produces all three in one call.

### TASK ###
Create a LinkedIn post and supporting metadata about the book below.

### INPUT ###
Book: "{{book_title}}"

Key points:
{{bullets_text}}

### CONSTRAINTS ###
- Do: write LINKEDIN as a single long-form post (150-250 words). Start with a strong hook line, then 3-4 short paragraphs of substance drawn from the key points, end with a question or call-to-action. Use blank lines between paragraphs.
- Do: write HOOKS as 3 alternative one-line openers (each under 120 chars), one per line prefixed "H: ".
- Do: write HASHTAGS as 8-15 hashtags (no # symbol), comma-separated on ONE line, prefixed "TAGS: ".
- Don't: include thinking process.
- Don't: output anything other than the three sections in the exact format below.

### OUTPUT FORMAT ###
Output ONLY:

LINKEDIN
<post>

HOOKS
H: ...
H: ...
H: ...

HASHTAGS
TAGS: tag1, tag2, tag3

### SUCCESS CRITERIA ###
A good answer has a 150-250 word LinkedIn post with a hook + paragraphs +
CTA, 3 hook variations under 120 chars, 8-15 hashtags, follows the exact
section format, and emits nothing else.
