Perform a security audit of the provided code:

## Check for:
1. **Injection** — SQL, NoSQL, command, LDAP injection
2. **Authentication** — weak auth, hardcoded credentials, missing MFA
3. **Authorization** — broken access control, IDOR, privilege escalation
4. **Data Exposure** — sensitive data in logs, unencrypted storage, PII leaks
5. **Configuration** — debug mode in prod, default credentials, open CORS
6. **Dependencies** — known CVEs, outdated packages
7. **Cryptography** — weak algorithms, hardcoded keys, improper random
8. **Input Validation** — missing sanitization, type confusion
9. **Error Handling** — stack traces exposed, verbose errors in prod
10. **Secrets** — API keys, tokens, passwords in code or config

## Output Format
For each vulnerability:
- **[CRITICAL/HIGH/MEDIUM/LOW]** — Title
- **Location**: file:line
- **Description**: what's wrong
- **Impact**: what could happen
- **Fix**: how to fix it
