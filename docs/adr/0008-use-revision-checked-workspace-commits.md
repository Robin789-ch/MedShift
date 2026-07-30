# Use revision-checked workspace commits

Every scenario save and agent-authored change set captures a base workspace revision and may commit only while that revision remains current. The Workspace module compares revisions, constructs and validates the next revision, and atomically replaces the file under one short application lock; stale changes fail without automatic merging. This optimistic approach avoids holding a lock across model calls or user confirmation while keeping delayed confirmation and persistence transitions explicit.
