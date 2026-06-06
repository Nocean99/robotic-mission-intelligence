# LinkedIn Post: Aegis SAR Benchmark

I evaluated Aegis on 5,712 annotated SAR images, then tested two API-review strategies.

A smarter review-priority sampling policy improved capture precision from 70% to 91% while keeping capture recall near 90%.

That matters because the goal is not just to detect something once. The goal is to preserve the right evidence for human review while reducing the amount of noise an analyst has to sort through.

The first API sample was balanced across positives and negatives. It preserved likely person evidence well, but still surfaced a lot of extra review items.

The second sample was selected more intentionally:

- highest review priority
- high uncertainty
- local misses or rejects
- a balanced benchmark slice

That harder sample produced a cleaner analyst queue without giving up much recall.

This is the direction I care about for Aegis: mission intelligence that can look at large volumes of sensor evidence, prioritize what matters, preserve uncertainty, and produce a useful mission record afterward.

Architecture matters, but measured behavior matters more.
