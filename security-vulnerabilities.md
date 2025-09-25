# Security Vulnerabilities - Priority Assessment

## Critical Priority (CVSS 9.0+)

| CVE ID | Package | Severity | CVSS Score | Description | Vulnerable Version | Fixed Version |
|--------|---------|----------|------------|-------------|-------------------|---------------|
| CVE-2025-43859 | h11 | Critical | 9.1 | h11 accepts some malformed Chunked-Encoding bodies | < 0.16.0 | 0.16.0 |

## High Priority (CVSS 7.0-8.9)

| CVE ID | Package | Severity | CVSS Score | Description | Vulnerable Version | Fixed Version |
|--------|---------|----------|------------|-------------|-------------------|---------------|
| CVE-2025-47287 | tornado | High | 7.5 | Tornado vulnerable to excessive logging caused by malformed multipart form data | < 6.5 | 6.5 |
| CVE-2024-23342 | ecdsa | High | 7.4 | Minerva timing attack on P-256 in python-ecdsa | >= 0 | No patch available |
| CVE-2025-4565 | protobuf | High | N/A | protobuf-python has a potential Denial of Service issue | >= 5.26.0rc1, < 5.29.5 | 5.29.5 |
| CVE-2025-53366 | mcp | High | N/A | MCP Python SDK vulnerability in the FastMCP Server causes validation error, leading to DoS | < 1.9.4 | 1.9.4 |
| CVE-2025-53365 | mcp | High | N/A | MCP Python SDK has Unhandled Exception in Streamable HTTP Transport, Leading to Denial of Service | < 1.10.0 | 1.10.0 |
| CVE-2025-47273 | setuptools | High | N/A | setuptools has a path traversal vulnerability in PackageIndex.download that leads to Arbitrary File Write | < 78.1.1 | 78.1.1 |

## Medium Priority (CVSS 4.0-6.9)

| CVE ID | Package | Severity | CVSS Score | Description | Vulnerable Version | Fixed Version |
|--------|---------|----------|------------|-------------|-------------------|---------------|
| CVE-2025-54121 | starlette | Medium | 5.3 | Starlette has possible denial-of-service vector when parsing large files in multipart forms | < 0.47.2 | 0.47.2 |
| CVE-2025-50182 | urllib3 | Medium | 5.3 | urllib3 does not control redirects in browsers and Node.js | >= 2.2.0, < 2.5.0 | 2.5.0 |
| CVE-2025-50181 | urllib3 | Medium | 5.3 | urllib3 redirects are not disabled when retries are disabled on PoolManager instantiation | < 2.5.0 | 2.5.0 |
| CVE-2024-47081 | requests | Medium | 5.3 | Requests vulnerable to .netrc credentials leak via malicious URLs | < 2.32.4 | 2.32.4 |

## Action Items

### Immediate (Critical/High Priority)
- [ ] **URGENT**: Update h11 to version 0.16.0+ (Critical vulnerability - CVSS 9.1)
- [ ] Update tornado to version 6.5+
- [ ] Update protobuf to version 5.29.5+
- [ ] Update mcp to version 1.10.0+ (addresses both CVE-2025-53366 and CVE-2025-53365)
- [ ] Update setuptools to version 78.1.1+
- [ ] **Review ecdsa usage** - No patch available for CVE-2024-23342, consider alternatives

### Short Term (Medium Priority)
- [ ] Update starlette to version 0.47.2+
- [ ] Update urllib3 to version 2.5.0+
- [ ] Update requests to version 2.32.4+

### Assessment Notes
- **Total vulnerabilities**: 19 alerts (1 Critical, 6 High, 4 Medium)
- **Packages affected**: h11, tornado, ecdsa, protobuf, mcp, setuptools, starlette, urllib3, requests
- **Duplicates found**: Several CVEs appear multiple times in the alerts

## Remediation Strategy

1. **Immediate**: Address the critical h11 vulnerability (CVSS 9.1) first
2. **High Priority**: Focus on DoS vulnerabilities in tornado, protobuf, and mcp packages
3. **Special Attention**: ecdsa package has no available patch - evaluate if cryptographic operations can use alternative libraries
4. **Medium Priority**: Update remaining packages during next maintenance window

## Last Updated
Generated: $(date)  
Source: GitHub Dependabot Security Advisories  
Repository: https://github.com/mcafee-eng/bond-ai