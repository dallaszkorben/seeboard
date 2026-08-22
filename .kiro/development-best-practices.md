# seeBoard Development Best Practices

## Debug Logs - REMOVE IMMEDIATELY

**Rule:** Debug logs and temporary print statements must be removed as soon as the issue they're debugging is resolved. Do NOT deploy code with debug logs still in place.

**Workflow:**
1. Add debug logs to identify the problem
2. Deploy and test to verify the fix
3. **IMMEDIATELY remove all debug/temporary logs**
4. Deploy the clean version
5. Never leave debug logs in deployed code

**Why:** 
- Keeps codebase clean and production-ready
- Avoids log clutter that obscures real issues
- Prevents accidentally shipping debug output to end users
- Shows professional code discipline

**Lesson learned:** Grace period slider debugging (2026-08-21) - left debug prints in deployed code for multiple iterations instead of cleaning them up immediately after each fix.
