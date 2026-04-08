# Findings & Decisions

## Requirements
- Improve the Reddit environment so navigation feels stable and the app behaves like a solid benchmark environment.
- Focus on code-level fixes inside the local repo.

## Research Findings
- Most internal Reddit navigation already uses React Router rather than hard document reloads.
- The visible repeated flicker came from a rerender/refetch loop: `RedditShell` recreated `notify` on every rerender, page loaders depended on `notify`, and page effects reran after shell rerenders.
- `React.StrictMode` is enabled in the Reddit app entrypoint, which can amplify mount-time loading flashes during development.
- The Reddit frontend has an existing compile error in `Profile.tsx` because the page stores `user` as `Record<string, unknown>` instead of using the existing `UserProfile` type.
- Search keeps stale results when the query becomes empty because the page returns early without clearing `results`.
- The submit page exposes a spoiler option but does not send `is_spoiler` to the backend create-post endpoint.
- Several clickable non-link elements are missing keyboard activation support, including the Reddit title, post titles, notification rows, comment collapse bars, and subreddit cards.
- `PopularCommunities` sorts the `subreddits` prop in place, mutating upstream state.
- `PostCard` derives the link hostname with `new URL(...)` during render; an invalid user-entered URL can throw and break the page.
- The Reddit settings model existed in backend/frontend state, but most settings had no runtime effect until the shell owned settings state and exposed it through context.
- After the second pass, these settings now affect live behavior: `theme`, `reduce_animations`, `default_feed_sort`, `default_comment_sort`, `compact_view`, `show_nsfw`, `blur_nsfw`, `open_links_in_new_tab`, `show_online_status`, and `show_active_communities`.
- Some settings are still persistence-only and not yet reflected in UI behavior: `auto_play_media`, `country`, `language`, `allow_followers`, and the email-notification toggles.

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| Fix the shell/context instability first | It is the highest-value cause of repeated flashing on single clicks |
| Include a small batch of correctness/accessibility fixes in the same pass | These are low-risk and materially improve environment quality |
| Prefer preserving existing UX over broad architectural rewrites | The user asked to improve the environment, not redesign it |

## Issues Encountered
| Issue | Resolution |
|-------|------------|
| Previous planning files were still describing an old Amazon task | Rewrote planning files for the current Reddit task |
| Reddit typecheck fails before verification can be called clean | Fix the underlying profile typing issue as part of the pass |

## Resources
- `environments/reddit/src/Shell.tsx`
- `environments/reddit/src/main.tsx`
- `environments/reddit/src/components/PostCard.tsx`
- `environments/reddit/src/components/CommentThread.tsx`
- `environments/reddit/src/components/RightSidebar.tsx`
- `environments/reddit/src/pages/Post.tsx`
- `environments/reddit/src/pages/Profile.tsx`
- `environments/reddit/src/pages/Search.tsx`
- `environments/reddit/src/pages/Submit.tsx`
- `environments/reddit/src/pages/Notifications.tsx`
- `environments/reddit/src/utils.ts`

## Verification Findings
- `pnpm --filter @webagentbench/reddit typecheck` passes after tightening the user-profile typing contract.
- `pnpm --filter @webagentbench/reddit build` passes after the navigation and interaction fixes.
- `pnpm --filter @webagentbench/reddit typecheck` still passes after wiring live settings behavior.
- `pnpm --filter @webagentbench/reddit build` still passes after wiring live settings behavior.
- Remaining Reddit design debt is now concentrated in settings that are still stored but not surfaced in observable behavior.
