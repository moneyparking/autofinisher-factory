# Bug Fix Protocol
Philosophy: the testing system is the primary quality guarantor.
Our goal is to build a testing system that catches 100% of defects before they reach production.
If a bug reaches production, the root problem is the testing system, not the code.
Every bug fix follows these eight steps in order:
1. Analyze and reproduce requirements.
2. Write a failing test (red).
3. Identify the real root cause.
4. Design the proper fix.
5. Apply the fix.
6. Verify the fix (green).
7. Analyze consequences and related issues.
8. Audit the testing system (The most important step: Why did our tests miss this? Suggest improvements, scan for similar bugs).
