# Security

Personas are **untrusted prompt content**, not code.  Collig installs the files
as data and never executes anything from this repository.

- Do not add scripts, executables, symlinks, archives or install hooks.
- Do not include API keys, passwords, private keys or personal contact details.
- CI rejects high-confidence credential patterns and unexpected files.
- A dossier can still influence the model through its system-prompt text.  PR
  reviewers must read it for prompt-injection instructions, harassment, or
  instructions to exfiltrate data, not just for style.
- Report a malicious persona through the repository issue tracker; maintainers
  can revert or remove it.

The validator and the client both enforce slug safety, file size limits, required
fields and SHA-256 checksums.  A tampered file will not install.
