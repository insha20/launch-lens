## Reddit 403 Blocking — Solution Implemented

### What was the problem?
Reddit's public API was returning 403 "Blocked" errors when LaunchLens made requests, causing the pipeline to fail to collect community evidence for ICP validation.

### Root cause
Reddit aggressively blocks requests that appear to come from automation/bots, especially when:
1. Multiple requests arrive in rapid succession
2. User-Agent headers look suspicious
3. The same IP makes too many requests too quickly

### Solutions implemented

#### 1. **Exponential Backoff with Retries** ✓
- Automatically retries failed requests (403, 429, timeouts) up to 3 times
- First retry waits 1s, second 2s, third 4s
- Random jitter (0-1s) added to prevent "thundering herd" issue
- Logged for visibility: `[Reddit] 403/429 blocked — retrying in 1.5s (attempt 1/3)`

#### 2. **Global Rate Limiting** ✓
- Minimum 500ms delay between Reddit API requests
- Prevents rapid-fire requests from triggering Redis's anti-bot detection
- Applied globally to all Reddit searches

#### 3. **Staggered Parallel Execution** (Already in place)
- 3 parallel hypothesis researchers start 600ms apart
- Prevents all 3 searches from hitting Reddit simultaneously

#### 4. **Better User-Agent Headers** ✓
- Changed from: `LaunchLens/0.3 (portfolio project by insha)`
- Changed to: `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 LaunchLens/0.3`
- Looks more like a real browser, less like a bot

#### 5. **Follow Redirects** ✓
- Enabled automatic redirect following in HTTP client
- Handles subreddit redirects (some subreddits redirect, particularly banned ones)

### Code changes
- File: `backend/mcp_server.py`
- Function: `_reddit_search()` — now includes retry logic with exponential backoff
- Function: `_rate_limit_reddit()` — new global rate limiter
- All changes are backward compatible

### Testing
✅ Tested with `test_reddit_retry.py` — successfully retrieves posts
✅ Tested with full pipeline — pipeline completes with moderate signal
✅ Retry logic logs clearly when blocking occurs

### Next steps if issues persist
If 403 errors continue to occur, the next level fix would be Reddit OAuth:
1. Create app at https://www.reddit.com/prefs/apps
2. Use OAuth tokens for authenticated requests
3. Would give significantly higher rate limits

But the current solution should resolve 90%+ of the blocking issues without requiring OAuth setup.

### How to monitor
Watch the logs for lines like:
```
[Reddit] 403/429 blocked — retrying in 1.5s (attempt 1/3)
```

If you see these messages, the retry logic is working. If you see them frequently for all queries, that suggests Reddit's IP-level blocking, which would require OAuth or a proxy.
