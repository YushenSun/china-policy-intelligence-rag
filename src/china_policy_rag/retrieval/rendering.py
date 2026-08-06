"""Safe human-readable evidence rendering without generated claims."""

from .models import EvidenceBundle


def render_markdown(bundle: EvidenceBundle, excerpt_chars: int = 1200) -> str:
    """Render exact evidence text and provenance in compact Markdown."""
    blocks = [f"# Retrieved evidence\n\nQuery: `{bundle.original_query}`"]
    for item in bundle.evidence:
        location = item.page_reference or item.section_reference or "Not available"
        text = item.text[:excerpt_chars]
        blocks.append(
            f"## {item.rank}. {item.title}\n\n"
            f"- Issuer: {item.issuer}\n- Publication date: {item.publication_date}\n"
            f"- Jurisdiction: {item.jurisdiction}\n- Language: {item.language}\n"
            f"- Local path: {item.local_file_path}\n"
            f"- Source URL: {item.source_url or 'Not available'}\n"
            f"- Location: {location}\n- Chunk ID: `{item.chunk_id}`\n"
            f"- Scores: lexical={item.scores.lexical_score}, "
            f"semantic={item.scores.semantic_score}, fused={item.scores.fused_score}\n\n"
            f"**Exact retrieved source text:**\n\n> {text.replace(chr(10), chr(10) + '> ')}"
        )
    return "\n\n".join(blocks) + "\n"
