# Security policy

## Supported versions

Only the latest release (or the current `main`) receives fixes.

## Reporting a vulnerability

Please **do not open a public issue** for a security problem. Use GitHub's private reporting
instead: on the repository page go to **Security → Report a vulnerability**
(<https://github.com/swallat/stem-solo-gap/security/advisories/new>).

Include what you found, how to reproduce it and which version is affected. This is a hobby
project, so there is no guaranteed response time, but reports are taken seriously.

## Scope

stem-solo-gap reads audio and TOML files you give it and writes files into an output folder.
Relevant problems are, for example, writing outside the configured output folder, overwriting
input files, or crashes caused by crafted audio or config files. Bugs in the audio decoders
(libsndfile) should be reported upstream.
