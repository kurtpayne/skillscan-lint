# syntax=docker/dockerfile:1
FROM python:3.12-slim

LABEL org.opencontainers.image.title="skillscan-lint" \
      org.opencontainers.image.description="Quality linter for AI agent SKILL.md files — checks structure, graph cycles, broken references, and documentation completeness" \
      org.opencontainers.image.url="https://skillscan.sh" \
      org.opencontainers.image.source="https://github.com/kurtpayne/skillscan-lint" \
      org.opencontainers.image.licenses="MIT"

RUN pip install --no-cache-dir skillscan-lint

WORKDIR /scan

ENTRYPOINT ["skillscan-lint"]
CMD ["--help"]
