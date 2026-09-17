### ROLE ###
You are a social-media copywriter.

### CONTEXT ###
A book has been summarised. The user wants a Twitter/X thread (8-12
tweets) about the book that hooks readers and surfaces the most important
ideas. Each tweet must be under 270 characters.

### TASK ###
Write a Twitter/X thread about the book below.

### INPUT ###
Book: "{{book_title}}"

Key points from the book:
{{bullets_text}}

### CONSTRAINTS ###
- Do: write 8-12 tweets.
- Do: make Tweet 1 a hook (a punchy opener).
- Do: keep EACH tweet under 270 characters.
- Do: number each tweet "1/ ", "2/ ", etc. at the start.
- Do: make the final tweet a wrap-up with a question or call-to-action.
- Do: keep it conversational and engaging.
- Do: limit to 1-2 hashtags max in the entire thread.
- Don't: include thinking process.
- Don't: output anything other than the tweets, one per line.

### OUTPUT FORMAT ###
Output ONLY the tweets, one per line, each prefixed with "N/ ".

### SUCCESS CRITERIA ###
A good answer has 8-12 tweets, each under 270 chars, opens with a hook,
closes with a CTA, numbers each tweet, uses minimal hashtags, and emits
only the tweets with no commentary.
