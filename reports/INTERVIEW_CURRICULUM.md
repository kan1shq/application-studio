# Unified interview curriculum

Software/backend and modern AI engineering; day70 readiness checkpoint with AI implementation depth continuing through February.

Use the existing 80 linked targets in the 60-minute weekday budget through day70; defer companion problems when needed. After day70, maintain weak patterns and mocks inside 30 minutes/day.

80 scheduled targets: 16 Easy, 52 Medium and 12 Hard. Six classic hard-pattern exercises replace medium slots; displaced mediums remain linked on the affected days as optional prerequisites. No repeat-frequency guarantee; master the pattern rather than memorize code.

Edition not assumed. First-edition chapter hints are labeled; use equivalent topic headings in second edition. Read selected sections, not whole chapters in a 20-minute slot. DDIA complements rather than replaces timed interview design.

## Shared readiness evidence

At day 70: three independent coding mocks, three design mocks scored with the 0–20 rubric, six ownership stories and two explainable projects. Evidence must distinguish hints, AI assistance and measured outcomes.

## Week 1: Arrays, hashing and complexity

Project: Where did my disk space actually go?

- [LC 1: Two Sum](https://leetcode.com/problems/two-sum/) — Easy (`dsa:lc-1`)
- [LC 217: Contains Duplicate](https://leetcode.com/problems/contains-duplicate/) — Easy (`dsa:lc-217`)
- [LC 242: Valid Anagram](https://leetcode.com/problems/valid-anagram/) — Easy (`dsa:lc-242`)
- [LC 49: Group Anagrams](https://leetcode.com/problems/group-anagrams/) — Medium (`dsa:lc-49`)
- [LC 347: Top K Frequent Elements](https://leetcode.com/problems/top-k-frequent-elements/) — Medium (`dsa:lc-347`)
- [LC 238: Product of Array Except Self](https://leetcode.com/problems/product-of-array-except-self/) — Medium (`dsa:lc-238`)
- [LC 128: Longest Consecutive Sequence](https://leetcode.com/problems/longest-consecutive-sequence/) — Medium (`dsa:lc-128`)
- [LC 36: Valid Sudoku](https://leetcode.com/problems/valid-sudoku/) — Medium (`dsa:lc-36`)

System design:
- Requirements and SLIs: latency, throughput, availability; estimate QPS and bytes
- HTTP/DNS/TLS, load balancers, stateless services and pagination
- Relational/document models, keys, normalization and ownership
- B-tree/LSM trade-offs, indexes and query plans
- Design a read-only media inventory/search API

Friday mock: inventory/search API
Reading: 1e chapters 1-3; 2e chapters 2-4: reliability, data models and storage. Networking/API mechanics use supplementary docs.

## Week 2: Two pointers and sliding windows

Project: Is Polars better for my workload?

- [LC 125: Valid Palindrome](https://leetcode.com/problems/valid-palindrome/) — Easy (`dsa:lc-125`)
- [LC 167: Two Sum II Input Array Is Sorted](https://leetcode.com/problems/two-sum-ii-input-array-is-sorted/) — Medium (`dsa:lc-167`)
- [LC 15: 3Sum](https://leetcode.com/problems/3sum/) — Medium (`dsa:lc-15`)
- [LC 11: Container With Most Water](https://leetcode.com/problems/container-with-most-water/) — Medium (`dsa:lc-11`)
- [LC 121: Best Time to Buy and Sell Stock](https://leetcode.com/problems/best-time-to-buy-and-sell-stock/) — Easy (`dsa:lc-121`)
- [LC 3: Longest Substring Without Repeating Characters](https://leetcode.com/problems/longest-substring-without-repeating-characters/) — Medium (`dsa:lc-3`)
- [LC 424: Longest Repeating Character Replacement](https://leetcode.com/problems/longest-repeating-character-replacement/) — Medium (`dsa:lc-424`)
- [LC 239: Sliding Window Maximum](https://leetcode.com/problems/sliding-window-maximum/) — Hard (`dsa:lc-239`)

System design:
- OLTP versus OLAP, columnar storage and analytical access patterns
- Batch ingestion, joins, bounded memory and external sorting
- Schema evolution, compatibility and data contracts
- Idempotent ingestion, backfills, checkpoints and validation
- Design a daily analytics ingestion pipeline

Friday mock: analytics ingestion pipeline
Reading: 1e chapters 3,4,10; 2e Storage and Retrieval, Encoding and Evolution, Batch Processing. Select relevant sections only.

## Week 3: Stacks and binary search

Project: Can I trust this model’s structured answer?

- [LC 20: Valid Parentheses](https://leetcode.com/problems/valid-parentheses/) — Easy (`dsa:lc-20`)
- [LC 155: Min Stack](https://leetcode.com/problems/min-stack/) — Medium (`dsa:lc-155`)
- [LC 739: Daily Temperatures](https://leetcode.com/problems/daily-temperatures/) — Medium (`dsa:lc-739`)
- [LC 84: Largest Rectangle in Histogram](https://leetcode.com/problems/largest-rectangle-in-histogram/) — Hard (`dsa:lc-84`)
- [LC 704: Binary Search](https://leetcode.com/problems/binary-search/) — Easy (`dsa:lc-704`)
- [LC 74: Search a 2D Matrix](https://leetcode.com/problems/search-a-2d-matrix/) — Medium (`dsa:lc-74`)
- [LC 875: Koko Eating Bananas](https://leetcode.com/problems/koko-eating-bananas/) — Medium (`dsa:lc-875`)
- [LC 33: Search in Rotated Sorted Array](https://leetcode.com/problems/search-in-rotated-sorted-array/) — Medium (`dsa:lc-33`)

System design:
- ACID and transaction boundaries in a real request
- Isolation, lost updates, write skew and optimistic concurrency
- Replication lag and read-your-writes requirements
- Leader/follower failover, durability and recovery objectives
- Design ticket reservation with inventory correctness

Friday mock: ticket reservation service
Reading: 1e chapters 5,7; 2e Replication and Transactions: choose guarantees from the use case.

## Week 4: Linked lists and cache design

Project: Find the scene I vaguely remember

- [LC 206: Reverse Linked List](https://leetcode.com/problems/reverse-linked-list/) — Easy (`dsa:lc-206`)
- [LC 21: Merge Two Sorted Lists](https://leetcode.com/problems/merge-two-sorted-lists/) — Easy (`dsa:lc-21`)
- [LC 141: Linked List Cycle](https://leetcode.com/problems/linked-list-cycle/) — Easy (`dsa:lc-141`)
- [LC 19: Remove Nth Node From End of List](https://leetcode.com/problems/remove-nth-node-from-end-of-list/) — Medium (`dsa:lc-19`)
- [LC 143: Reorder List](https://leetcode.com/problems/reorder-list/) — Medium (`dsa:lc-143`)
- [LC 138: Copy List with Random Pointer](https://leetcode.com/problems/copy-list-with-random-pointer/) — Medium (`dsa:lc-138`)
- [LC 146: LRU Cache](https://leetcode.com/problems/lru-cache/) — Medium (`dsa:lc-146`)
- [LC 23: Merge k Sorted Lists](https://leetcode.com/problems/merge-k-sorted-lists/) — Hard (`dsa:lc-23`)

System design:
- Sharding keys, skew and hot partitions
- Cache-aside, invalidation, stampedes and TTL trade-offs
- Inverted versus vector indexes; exact/approximate retrieval trade-offs
- Index refresh, deletes, access filtering and reindexing
- Design user-scoped subtitle search

Friday mock: subtitle search service
Reading: 1e chapters 3,6; 2e Storage and Retrieval and Sharding. Vector operations use Qdrant docs.

## Week 5: Trees and BST invariants

Project: A spoiler-aware film companion

- [LC 104: Maximum Depth of Binary Tree](https://leetcode.com/problems/maximum-depth-of-binary-tree/) — Easy (`dsa:lc-104`)
- [LC 226: Invert Binary Tree](https://leetcode.com/problems/invert-binary-tree/) — Easy (`dsa:lc-226`)
- [LC 543: Diameter of Binary Tree](https://leetcode.com/problems/diameter-of-binary-tree/) — Easy (`dsa:lc-543`)
- [LC 102: Binary Tree Level Order Traversal](https://leetcode.com/problems/binary-tree-level-order-traversal/) — Medium (`dsa:lc-102`)
- [LC 98: Validate Binary Search Tree](https://leetcode.com/problems/validate-binary-search-tree/) — Medium (`dsa:lc-98`)
- [LC 230: Kth Smallest Element in a BST](https://leetcode.com/problems/kth-smallest-element-in-a-bst/) — Medium (`dsa:lc-230`)
- [LC 124: Binary Tree Maximum Path Sum](https://leetcode.com/problems/binary-tree-maximum-path-sum/) — Hard (`dsa:lc-124`)
- [LC 236: Lowest Common Ancestor of a Binary Tree](https://leetcode.com/problems/lowest-common-ancestor-of-a-binary-tree/) — Medium (`dsa:lc-236`)

System design:
- Queue versus log, consumer groups and partition ordering
- At-least-once delivery, duplicate handling and dead-letter queues
- Outbox/CDC, event schema changes and replay safety
- Windowing, event time, late data and stream joins
- Design notifications for media requests

Friday mock: notification service
Reading: 1e chapters 4,11; 2e Encoding and Evolution and Stream Processing. Relate to Kafka experience, not just vocabulary.

## Week 6: Heaps, tries and backtracking

Project: What can my local model comfortably handle?

- [LC 215: Kth Largest Element in an Array](https://leetcode.com/problems/kth-largest-element-in-an-array/) — Medium (`dsa:lc-215`)
- [LC 973: K Closest Points to Origin](https://leetcode.com/problems/k-closest-points-to-origin/) — Medium (`dsa:lc-973`)
- [LC 621: Task Scheduler](https://leetcode.com/problems/task-scheduler/) — Medium (`dsa:lc-621`)
- [LC 208: Implement Trie Prefix Tree](https://leetcode.com/problems/implement-trie-prefix-tree/) — Medium (`dsa:lc-208`)
- [LC 211: Design Add and Search Words Data Structure](https://leetcode.com/problems/design-add-and-search-words-data-structure/) — Medium (`dsa:lc-211`)
- [LC 78: Subsets](https://leetcode.com/problems/subsets/) — Medium (`dsa:lc-78`)
- [LC 39: Combination Sum](https://leetcode.com/problems/combination-sum/) — Medium (`dsa:lc-39`)
- [LC 212: Word Search II](https://leetcode.com/problems/word-search-ii/) — Hard (`dsa:lc-212`)

System design:
- Partial failures, timeouts, retries, jitter and retry storms
- Admission control, backpressure, rate limiting and fair queues
- Consistency versus availability during partitions; linearizability examples
- Consensus, leader election, fencing and distributed-lock limitations
- Design a capacity-bounded inference API

Friday mock: inference API
Reading: 1e chapters 8,9; 2e The Trouble with Distributed Systems and Consistency and Consensus. Depth is trade-offs, not implementing Raft.

## Week 7: Graphs, topological order, union-find and shortest paths

Project: No, I meant the other player: voice correction

- [LC 200: Number of Islands](https://leetcode.com/problems/number-of-islands/) — Medium (`dsa:lc-200`)
- [LC 133: Clone Graph](https://leetcode.com/problems/clone-graph/) — Medium (`dsa:lc-133`)
- [LC 994: Rotting Oranges](https://leetcode.com/problems/rotting-oranges/) — Medium (`dsa:lc-994`)
- [LC 207: Course Schedule](https://leetcode.com/problems/course-schedule/) — Medium (`dsa:lc-207`)
- [LC 210: Course Schedule II](https://leetcode.com/problems/course-schedule-ii/) — Medium (`dsa:lc-210`)
- [LC 417: Pacific Atlantic Water Flow](https://leetcode.com/problems/pacific-atlantic-water-flow/) — Medium (`dsa:lc-417`)
- [LC 684: Redundant Connection](https://leetcode.com/problems/redundant-connection/) — Medium (`dsa:lc-684`)
- [LC 743: Network Delay Time](https://leetcode.com/problems/network-delay-time/) — Medium (`dsa:lc-743`)

System design:
- WebSockets/SSE and connection lifecycles; streaming versus request/response
- Latency budgets, tail amplification and end-to-end tracing
- Cancellation, disconnects and late results across services
- Object storage, CDN delivery, chunking and adaptive bitrate concepts
- Design a voice-enabled media lookup service

Friday mock: voice/media lookup service
Reading: 1e chapters 1,8; 2e Defining Nonfunctional Requirements and partial-failure sections. Media/transport mechanics require supplementary docs.

## Week 8: Dynamic programming

Project: Give an AI a useful read-only tool

- [LC 70: Climbing Stairs](https://leetcode.com/problems/climbing-stairs/) — Easy (`dsa:lc-70`)
- [LC 198: House Robber](https://leetcode.com/problems/house-robber/) — Medium (`dsa:lc-198`)
- [LC 213: House Robber II](https://leetcode.com/problems/house-robber-ii/) — Medium (`dsa:lc-213`)
- [LC 322: Coin Change](https://leetcode.com/problems/coin-change/) — Medium (`dsa:lc-322`)
- [LC 300: Longest Increasing Subsequence](https://leetcode.com/problems/longest-increasing-subsequence/) — Medium (`dsa:lc-300`)
- [LC 139: Word Break](https://leetcode.com/problems/word-break/) — Medium (`dsa:lc-139`)
- [LC 312: Burst Balloons](https://leetcode.com/problems/burst-balloons/) — Hard (`dsa:lc-312`)
- [LC 1143: Longest Common Subsequence](https://leetcode.com/problems/longest-common-subsequence/) — Medium (`dsa:lc-1143`)

System design:
- Authentication versus authorization; user/tenant ownership
- API tokens/OAuth concepts, least privilege and secret boundaries
- LLD: typed interfaces, error contracts, dependency injection and test doubles
- Async/concurrency limits, thread safety and bounded resource pools
- Design a secure read-only integration API

Friday mock: read-only integration API
Reading: 1e chapters 4,8 plus supplementary OWASP/API docs; DDIA is not a complete auth or object-design textbook.

## Week 9: Intervals, greedy and bit manipulation

Project: Can pretrained embeddings organize my saved links?

- [LC 56: Merge Intervals](https://leetcode.com/problems/merge-intervals/) — Medium (`dsa:lc-56`)
- [LC 57: Insert Interval](https://leetcode.com/problems/insert-interval/) — Medium (`dsa:lc-57`)
- [LC 435: Non-overlapping Intervals](https://leetcode.com/problems/non-overlapping-intervals/) — Medium (`dsa:lc-435`)
- [LC 55: Jump Game](https://leetcode.com/problems/jump-game/) — Medium (`dsa:lc-55`)
- [LC 45: Jump Game II](https://leetcode.com/problems/jump-game-ii/) — Medium (`dsa:lc-45`)
- [LC 135: Candy](https://leetcode.com/problems/candy/) — Hard (`dsa:lc-135`)
- [LC 338: Counting Bits](https://leetcode.com/problems/counting-bits/) — Easy (`dsa:lc-338`)
- [LC 136: Single Number](https://leetcode.com/problems/single-number/) — Easy (`dsa:lc-136`)

System design:
- Metrics/logs/traces, SLOs, alerting and incident triage
- Deployments, compatibility, canaries, rollback and database migrations
- Backups, restore drills, disaster recovery and capacity headroom
- AI data/model versions, drift, feedback loops and privacy/deletion
- Design a bookmark classification and feedback service

Friday mock: classification/feedback service
Reading: 1e chapters 10-12; 2e Batch Processing, Stream Processing and application data-system trade-offs. Read selected passages, not entire chapters overnight.

## Week 10: Mixed transfer, selected hard problems and matrices

Project: Does this task actually need an agent?

- [LC 76: Minimum Window Substring](https://leetcode.com/problems/minimum-window-substring/) — Hard (`dsa:lc-76`)
- [LC 42: Trapping Rain Water](https://leetcode.com/problems/trapping-rain-water/) — Hard (`dsa:lc-42`)
- [LC 295: Find Median from Data Stream](https://leetcode.com/problems/find-median-from-data-stream/) — Hard (`dsa:lc-295`)
- [LC 297: Serialize and Deserialize Binary Tree](https://leetcode.com/problems/serialize-and-deserialize-binary-tree/) — Hard (`dsa:lc-297`)
- [LC 127: Word Ladder](https://leetcode.com/problems/word-ladder/) — Hard (`dsa:lc-127`)
- [LC 72: Edit Distance](https://leetcode.com/problems/edit-distance/) — Medium (`dsa:lc-72`)
- [LC 73: Set Matrix Zeroes](https://leetcode.com/problems/set-matrix-zeroes/) — Medium (`dsa:lc-73`)
- [LC 48: Rotate Image](https://leetcode.com/problems/rotate-image/) — Medium (`dsa:lc-48`)

System design:
- End-to-end design: requirements, estimates, data model and APIs
- Hot keys, fan-out, caching and growth bottlenecks
- Multi-region failure, consistency choices and cost trade-offs
- Compare deterministic tools versus agents; budgets, permission and eval boundaries
- Full design mock plus ownership/behavioral debrief

Friday mock: multi-user media discovery and request service
Reading: Revisit the weakest DDIA sections. Explain trade-offs without the book; no new cover-to-cover reading target.

## Week 11: Interview maintenance: weakest pattern and due retries

Project: Hybrid retrieval with a regression gate


System design:
- Request contracts and data ownership
- Timeouts, retries and failure recovery
- State, consistency and versioning
- Overload, observability and resource budgets
- Explain one design trade-off under changed requirements

Friday mock: Explain one design trade-off under changed requirements
Reading: Selected topic lookup only; use the current project’s primary sources.

## Week 12: Interview maintenance: weakest pattern and due retries

Project: Hybrid retrieval with a regression gate


System design:
- Request contracts and data ownership
- Timeouts, retries and failure recovery
- State, consistency and versioning
- Overload, observability and resource budgets
- Explain one design trade-off under changed requirements

Friday mock: Explain one design trade-off under changed requirements
Reading: Selected topic lookup only; use the current project’s primary sources.

## Week 13: Interview maintenance: weakest pattern and due retries

Project: A resumable evidence-gathering workflow


System design:
- Request contracts and data ownership
- Timeouts, retries and failure recovery
- State, consistency and versioning
- Overload, observability and resource budgets
- Explain one design trade-off under changed requirements

Friday mock: Explain one design trade-off under changed requirements
Reading: Selected topic lookup only; use the current project’s primary sources.

## Week 14: Interview maintenance: weakest pattern and due retries

Project: A resumable evidence-gathering workflow


System design:
- Request contracts and data ownership
- Timeouts, retries and failure recovery
- State, consistency and versioning
- Overload, observability and resource budgets
- Explain one design trade-off under changed requirements

Friday mock: Explain one design trade-off under changed requirements
Reading: Selected topic lookup only; use the current project’s primary sources.

## Week 15: Interview maintenance: weakest pattern and due retries

Project: MCP client/server boundaries under failure


System design:
- Request contracts and data ownership
- Timeouts, retries and failure recovery
- State, consistency and versioning
- Overload, observability and resource budgets
- Explain one design trade-off under changed requirements

Friday mock: Explain one design trade-off under changed requirements
Reading: Selected topic lookup only; use the current project’s primary sources.

## Week 16: Interview maintenance: weakest pattern and due retries

Project: MCP client/server boundaries under failure


System design:
- Request contracts and data ownership
- Timeouts, retries and failure recovery
- State, consistency and versioning
- Overload, observability and resource budgets
- Explain one design trade-off under changed requirements

Friday mock: Explain one design trade-off under changed requirements
Reading: Selected topic lookup only; use the current project’s primary sources.

## Week 17: Interview maintenance: weakest pattern and due retries

Project: Grounded visual and voice correction


System design:
- Request contracts and data ownership
- Timeouts, retries and failure recovery
- State, consistency and versioning
- Overload, observability and resource budgets
- Explain one design trade-off under changed requirements

Friday mock: Explain one design trade-off under changed requirements
Reading: Selected topic lookup only; use the current project’s primary sources.

## Week 18: Interview maintenance: weakest pattern and due retries

Project: Grounded visual and voice correction


System design:
- Request contracts and data ownership
- Timeouts, retries and failure recovery
- State, consistency and versioning
- Overload, observability and resource budgets
- Explain one design trade-off under changed requirements

Friday mock: Explain one design trade-off under changed requirements
Reading: Selected topic lookup only; use the current project’s primary sources.

## Week 19: Interview maintenance: weakest pattern and due retries

Project: Measured inference gateway and operating limits


System design:
- Request contracts and data ownership
- Timeouts, retries and failure recovery
- State, consistency and versioning
- Overload, observability and resource budgets
- Explain one design trade-off under changed requirements

Friday mock: Explain one design trade-off under changed requirements
Reading: Selected topic lookup only; use the current project’s primary sources.

## Week 20: Interview maintenance: weakest pattern and due retries

Project: Measured inference gateway and operating limits


System design:
- Request contracts and data ownership
- Timeouts, retries and failure recovery
- State, consistency and versioning
- Overload, observability and resource budgets
- Explain one design trade-off under changed requirements

Friday mock: Explain one design trade-off under changed requirements
Reading: Selected topic lookup only; use the current project’s primary sources.

## Day 42: Mid-cycle diagnostic

- Review coding error patterns and one timed design explanation.
- Inspect one AI evaluation scorecard and a source-supported answer.
- Cut optional build scope if interview gaps are growing.

Evidence IDs: dsa:mock-w4, systems:day-40, milestone:weekend_1:build, milestone:weekend_1:evaluate, milestone:weekend_1:explain, milestone:weekend_4:build, milestone:weekend_4:evaluate, milestone:weekend_4:explain, career:day-5, career:day-12, career:day-19, career:day-26, career:day-33, career:day-40

## Day 56: Interview rehearsal

- Run coding and design mocks inside existing study slots.
- Select two explainable builds and prepare six experience stories.
- Use remaining starter weekends for evidence and weak areas when needed.

Evidence IDs: dsa:mock-w4, dsa:mock-w7, systems:day-40, systems:day-54, milestone:weekend_1:build, milestone:weekend_1:evaluate, milestone:weekend_1:explain, milestone:weekend_4:build, milestone:weekend_4:evaluate, milestone:weekend_4:explain, career:day-5, career:day-12, career:day-19, career:day-26, career:day-33, career:day-40

## Day 70: Interview readiness

- Three independent coding mocks with invariants, complexity and edge cases.
- Three system-design mocks scored with the shared 0–20 rubric.
- Six experience stories with personal, team and AI-assisted contributions separated.
- Two runnable, explainable projects with evaluation boundaries and honest limitations.

Evidence IDs: dsa:mock-w4, dsa:mock-w7, dsa:mock-w10, systems:day-40, systems:day-54, systems:day-68, milestone:weekend_1:build, milestone:weekend_1:evaluate, milestone:weekend_1:explain, milestone:weekend_4:build, milestone:weekend_4:evaluate, milestone:weekend_4:explain, career:day-5, career:day-12, career:day-19, career:day-26, career:day-33, career:day-40

## Day 140: Modern AI capability

- Reproduce a retrieval regression evaluation.
- Resume and bound an agent workflow with controlled side effects.
- Explain and test MCP trust boundaries.
- Ground multimodal outputs and handle uncertainty.
- Measure serving behavior under a bounded workload.

Evidence IDs: dsa:mock-w4, dsa:mock-w7, dsa:mock-w10, systems:day-40, systems:day-54, systems:day-68, milestone:weekend_1:build, milestone:weekend_1:evaluate, milestone:weekend_1:explain, milestone:weekend_4:build, milestone:weekend_4:evaluate, milestone:weekend_4:explain, career:day-5, career:day-12, career:day-19, career:day-26, career:day-33, career:day-40

## Evidence sources

- [Company-wise LeetCode repository](https://github.com/krishnadey30/LeetCode-Questions-CompanyWise): Latest repository commit checked through GitHub API: 2023-04-01, fb5f78b55eead7f948aada8459c5bfd31ae8abbc. The 6months filenames are historical windows, NOT the last six months of 2026. Collection methodology/current frequency are not verified; use for variants, not predictions.
- [Amazon SDE II preparation](https://amazon.jobs/content/en-gb/how-we-hire/sde-ii-interview-prep): Published guidance includes coding, system design and behavioral assessment; expect runnable, tested code. Confirm the actual invitation format.
- [Microsoft technical interviews](https://careers.microsoft.com/v2/global/en/hiring-tips/technical-interviewing): Practice problem solving, coding, testing and role-relevant design; communicate assumptions and trade-offs.
- [Meta E4 Bangalore experience](https://www.reddit.com/r/leetcode/comments/1p35b98/meta_e4_software_product_interview_experience/): One account describes DSA plus AI-enabled codebase work. Not a universal format, difficulty distribution or verified outcome.
- [Amazon SDE2 Bengaluru experience](https://www.reddit.com/r/leetcode/comments/1kazu6q/amazon_sde2_reject/): One account describes coding, low/high-level design and behavioral rounds. Use as breadth evidence, not a list of predicted questions.
- [NeetCode 150](https://neetcode.io/practice/practice/neetcode150): Primary pattern roadmap. Its difficulty mix is medium-heavy; list completion is not a hiring threshold.
- [LeetCode Top Interview 150](https://leetcode.com/studyplan/top-interview-150/): Supplementary coverage and unseen variants, not a second compulsory 150. The page suggests 3+ months.
- [DDIA first edition contents](https://www.oreilly.com/library/view/designing-data-intensive-applications/9781491903063/): Use selected topic sections and produce design artifacts; do not read passively.
- [DDIA second edition contents](https://www.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/): Chapter numbers differ. Use topic headings if you own the second edition; edition is unconfirmed.
