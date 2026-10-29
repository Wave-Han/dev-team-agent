"""
Security layer - boundary defense against prompt injection.

Design decision (the security flavor of the P/R seesaw):
patterns are kept DELIBERATELY NARROW - only explicit "discard your
instructions" phrasings. A wide filter would also block benign text
that merely contains a word like "忽略" (e.g. "忽略大小写"), breaking
the product to feel safe. Narrowness means variants can slip through;
that residual risk is handled by the layers behind the boundary
(output invariant, reviewer, no-progress guard).
"""

import re

# (pattern, label) - explicit override phrasings only
OVERRIDE_PATTERNS = [
    (r"忽略(以上|之前|上面|所有)+(的)?(指令|要求|规则|设定)", "override-instruction-zh"),
    (r"(?i)ignore\s+(all\s+)?(previous|prior|above)\s+(instructions?|rules?|prompts?)",
     "override-instruction-en"),
    (r"(?i)disregard\s+(all\s+)?(previous|prior|above)", "override-instruction-en"),
]


class InputSanitizer:
    """Checks untrusted user input for high-risk override payloads."""

    def __init__(self, patterns=None):
        self.patterns = patterns or OVERRIDE_PATTERNS

    def check(self, text):
        """Return a violation label, or None if the input looks clean."""
        for pattern, label in self.patterns:
            if re.search(pattern, text):
                return label
        return None
