# Conversion Log: V0519_1_ch9_rebenchmark (repeatability harness)

Started at: 2026-09-28T12:14:29

<!-- generated-by: Elixir v0.5.19.1 | run_id=20260928-121429-8b2f3b9b | harness=scripts/repeatability_run.py -->

---

[12:14:29] [SUCCESS] 🚀 Repeatability run — headless end-to-end chapter pipeline
[12:14:29] [INFO]   Chapter file: source.md
[12:14:29] [INFO]   Heading: '9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS'
[12:14:29] [INFO]   Source: 7030 words / 50107 chars
[12:14:29] [INFO]   Frontmatter: {"title": "9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS", "book": "Broken Structures Salman Akhtar", "source_fil
[12:14:29] [INFO]   Endpoint: http://localhost:3031 (model glm-4-plus)
[12:14:29] [INFO]   Run id: 20260928-121429-8b2f3b9b (app 0.5.19.1)
[12:14:30] [INFO] ━━━ Conversion Settings (repeatability harness) ━━━
[12:14:30] [INFO]   provider=llamacpp
[12:14:30] [INFO]   model=glm-4-plus
[12:14:30] [INFO]   t=0.70
[12:14:30] [INFO]   max_context=128000
[12:14:30] [INFO]   max_output=32768
[12:14:30] [INFO]   coverage_floor=0.85
[12:14:30] [INFO]   overdeliver=True
[12:14:30] [INFO]   workers=1
[12:14:30] [INFO]   lang=en
[12:14:30] [INFO]   Layer8=disabled (local backend)
[12:14:30] [DEBUG]     🔧 HTTP timeout set to 600s (local mode)
[12:14:30] [DEBUG]   🎛️ Model profile: Default
[12:14:30] [INFO]   ℹ️ Heavy model fallback disabled (same as primary or empty).
[12:14:30] [INFO]   📝 Max output tokens: 32768 (context: 128000)
[12:14:30] [INFO]   Summarizer built (primary_model='glm-4-plus')
[12:14:31] [INFO]   📊 V17.2 Deterministic analysis: 1/1 segments analyzed → 001_9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS_analysis.md
[12:14:31] [INFO]     🎯 V15.2.0: Enhanced concept extraction starting (6 techniques)
[12:14:31] [DEBUG]     🎯 V15.2.0 #1 (intro+conclusion): 4 concepts — ['Charles Simic', 'Libidinal Types', 'Social Functioning Any', 'Related Differences Some']
[12:14:31] [DEBUG]     🎯 V15.2.0 #2 (proper-noun theorists): 15 concepts — ['Bleuler', 'Kernberg', 'Zetzel', 'Cooper', 'Lazare']
[12:14:31] [DEBUG]     🎯 V15.2.0 #3 (section headings): 2 concepts — ['Histrionic And Schizotypal\nPersonality Disorders', 'Mixed Forms And Extrinsic Influences On\nSymptomatology']
[12:14:31] [DEBUG]     🎯 V15.2.0 #4 (conclusion lists): 4 concepts — ['mixed forms', 'level of social functioning', 'sex-related differences', 'changes in symptomatology over the life span, and']
[12:14:31] [DEBUG]     🎯 V15.2.0 #5: LLM-assisted concept extraction starting...
[12:14:31] [INFO]     🦙 llama.cpp (glm-4-plus) t=1.00 max=800 streaming…
[12:14:34] [DEBUG]     ✅ V15.2.0 #5: LLM extracted 20 concepts
[12:14:34] [DEBUG]     🎯 V15.2.0 #5 (LLM-assisted): 20 concepts — ['Histrionic Personality Disorder', 'Schizotypal Personality Disorder', 'DSM-III (1980)', 'DSM-III-R (1987)', 'Hysterical personality']
[12:14:34] [DEBUG]     🎯 V15.2.0: merged 45 concepts before source-grounding
[12:14:34] [DEBUG]     🎯 V15.2.0 #6 (source-grounded): kept 43, dropped 2 ghost concepts — dropped: ['Freud 1931 "Libidinal Types"', 'Reich 1933']
[12:14:34] [INFO]     🎯 V15.2.0: FINAL 43 concepts (cap 50)
[12:14:34] [INFO]   🎯 43 concepts extracted (llm_assisted=True), 0 callouts
[12:14:34] [SUCCESS] 🚀 summarize_chapters() — the full 16-stage pipeline…
[12:14:34] [INFO] 📚 Summarising 1 chapters with 1 worker(s)...
[12:14:34] [INFO] 📚 Chapter 1/1: 9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS…
[12:14:34] [DEBUG]     [V17.5] Searching for analysis files in: /home/z/elixir/runs/ch9_v0519_1
[12:14:34] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS_analysis.md']
[12:14:34] [DEBUG]     [V17.5] Using analysis: 001_9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS_analysis.md (3911 chars), segment: 001_9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS.md
[12:14:34] [INFO]     📊 V17.2: Prepended deterministic analysis (3911 chars) — citation recall 78%→100%
[12:14:34] [INFO]     🧭 V0.10 (P6): strategy=single_pass (src=10,732 tok / window=128,000 / output=32,768) — adaptive window 128,000 > 32,768: src 10,732 <= usable 94,020 (window - output 32,768 - margin 700 - overhead 512)
[12:14:34] [INFO]     ⚡ Using primary model: glm-4-plus
[12:14:34] [DEBUG]     🎯 Injecting 43 concepts + 0 callouts into prompt
[12:14:34] [INFO]     📦 V0.4: master-summary architecture (default) — input 10732 tok, output cap 32768
[12:14:34] [INFO]     📦 V0.3 Call 1/3: Master Summary (comprehensive thorough)
[12:14:34] [INFO]     🤖 glm-4-plus (t=0.70) via llm_provider.llamacpp…
[12:14:34] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.70 max=32768 streaming…
[12:14:46] [INFO]     ✅ V0.3 Call 1/3: master summary = 416 words, 3452 chars
[12:14:46] [INFO]     📦 V0.3 Call 2/3: Derive bullet points from master summary
[12:14:46] [INFO]     🤖 glm-4-plus (t=0.70) via llm_provider.llamacpp…
[12:14:46] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.70 max=2048 streaming…
[12:14:54] [INFO]     ✅ V0.3 Call 2/3: 29 bullets derived from master summary
[12:14:54] [INFO]     📦 V0.3 Call 3/3: Derive executive summary from master + bullets
[12:14:54] [INFO]     🤖 glm-4-plus (t=0.70) via llm_provider.llamacpp…
[12:14:54] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.70 max=1024 streaming…
[12:14:57] [INFO]     ✅ V0.3 Call 3/3: exec summary = 169 words
[12:14:57] [INFO]     🤖 glm-4-plus (t=0.30) via llm_provider.llamacpp…
[12:14:57] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.30 max=8192 streaming…
[12:15:50] [INFO]     📖 V0.5.7 source glossary (separate call) → /home/z/elixir/runs/ch9_v0519_1/summaries/.glossaries/9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS.glossary.md
[12:15:50] [DEBUG]     📝 Parsed: exec=1399 chars, bullets=29, thorough=3452 chars
[12:15:50] [INFO]     📊 Primary coverage: 90% | keywords: ['personality', 'personality disorder', 'personality disorders', 'disorder', 'hysterical', 'disorders', 'hysterical personality', 'individuals']
[12:15:50] [DEBUG]     🔍 Coverage detail: 18/18 keywords found | missing: []
[12:15:50] [INFO]     📈 Coverage 90% < effective target 100% (over-deliver: floor 85% → target 100%) — applying 3-Tier Guarantee
[12:15:50] [DEBUG]     💾 V18.20.1.2: primary checkpoint saved (29 bullets, 169 exec words, 416 thorough words) → .checkpoints/primary_9_-_HISTRIONIC_AND_SCHIZOTYPAL_PERSONALITY_DISORDERS_summary.md
[12:15:51] [DEBUG]     🔍 Fact-check: all 29 bullets verified ✓
[12:15:51] [INFO]     📝 Additive sections missing — running followup call for distinctions + tensions…
[12:15:51] [INFO]     🤖 glm-4-plus (t=0.70) via llm_provider.llamacpp…
[12:15:51] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.70 max=4096 streaming…
[12:15:54] [WARNING]     ⚠️ V18.20.3.2: additive followup mass-truncation (5/8 lines would be dropped) — retrying the additive call once with a fresh generation
[12:15:54] [INFO]     🤖 glm-4-plus (t=0.70) via llm_provider.llamacpp…
[12:15:54] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.70 max=4096 streaming…
[12:15:59] [INFO]     ✅ V18.20.3.2: additive retry improved yield: 3 → 4 usable lines
[12:15:59] [INFO]     ✅ Additive sections via followup call: key_distinctions=495 chars, theoretical_tensions=425 chars (7/11 lines will be dropped as truncated)
[12:15:59] [DEBUG]     💾 V18.20.1.2: post-additive-sections checkpoint saved (29 bullets, 169 exec words, 416 thorough words, +key_distinctions, +theoretical_tensions) → .checkpoints/post-additive-sections_9_-_HISTRIONIC_AND_SCHIZOTYPAL_PERSONALITY_DISORDERS_summary.md
[12:15:59] [WARNING]     ⚠️ thorough_summary too short (416 words < 800 threshold) — requesting dedicated expansion…
[12:15:59] [INFO]     🤖 glm-4-plus (t=0.35) via llm_provider.llamacpp…
[12:15:59] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.35 max=8192 streaming…
[12:16:09] [INFO]     📖 Attempt 1/3: dedicated thorough = 313 words
[12:16:09] [DEBUG]     ⚠️ Attempt 1 empty/short — retrying with directive nudge after 3s
[12:16:12] [INFO]     🤖 glm-4-plus (t=0.35) via llm_provider.llamacpp…
[12:16:12] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.35 max=8192 streaming…
[12:16:19] [INFO]     📖 Attempt 2/3: dedicated thorough = 340 words
[12:16:19] [DEBUG]     ⚠️ Attempt 2 empty/short — retrying (attempt 3/3)
[12:16:19] [INFO]     🤖 glm-4-plus (t=0.35) via llm_provider.llamacpp…
[12:16:19] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.35 max=8192 streaming…
[12:16:26] [INFO]     📖 Attempt 3/3: dedicated thorough = 348 words
[12:16:26] [DEBUG]     📏 V0.4.38 F2: attempt 4 — re-prompting with a quantified length directive (best was 348 < 800 min words)
[12:16:26] [INFO]     🤖 glm-4-plus (t=0.35) via llm_provider.llamacpp…
[12:16:26] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.35 max=8192 streaming…
[12:16:49] [INFO]     📖 Attempt 4/4: dedicated thorough = 961 words (length-directive recovered)
[12:16:49] [INFO]     ✅ thorough_summary expanded via dedicated call: 416 → 961 words
[12:16:49] [INFO]     ⚠️ 29 bullets — requesting dedicated bullet expansion (full output budget)…
[12:16:49] [INFO]     🤖 glm-4-plus (t=0.70) via llm_provider.llamacpp…
[12:16:49] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.70 max=8192 streaming…
[12:17:02] [INFO]     ✅ Bullet expansion: 29 → 59 bullets (added 30 new via dedicated call)
[12:17:02] [INFO]     ✅ Final coverage 100%
[12:17:02] [DEBUG]     📏 F1: exec=169w, thorough=961w (source=7030w; targets exec<=250w, thorough<=3164w)
[12:17:02] [WARNING]     ⏭️  Phase 2.2: embedder unhealthy — skipping semantic fact-check (would produce false drops on zero-vector similarity, then recovery would resurrect them = churn)
[12:17:02] [DEBUG]     📖 F3: Reading level — source: 15.9, summary: 18.0 (diff: -2.1)
[12:17:02] [INFO]     ℹ️ F3: Summary is 2.1 grade levels denser than source — expected for a compressed academic summary.
[12:17:02] [DEBUG]     📊 I2: Chapter difficulty 0.52/1.0 (grade 15.9, strategy: multi_sample)
[12:17:02] [DEBUG]     🔄 J2: 30 cross-section redundancy(ies) found (exec↔bullets: 10, bullets↔thorough: 19)
[12:17:02] [DEBUG]     ✅ J3: Exec summary coherent (100/100, 3 markers)
[12:17:02] [DEBUG]     [V17.5] Analysis exists: 1 file(s) found — V17.4 skips ENABLED
[12:17:02] [INFO]     📊 V17.4: Deterministic analysis found — skipping old sequential gap-fill (V17.3 judge will handle it, saves ~20 min)
[12:17:02] [WARNING] ⚠️ Judge coverage reported 0% but this is a degenerate signal (embedder broken/unavailable), not a real 0%. Skipping gap-fill. The deterministic judge will verify actual coverage next.
[12:17:02] [INFO]     📊 Judge: coverage=100% (56/56 claims), grounding=0% (0/59 bullets), hallucinations=59, deviations=0 — ❌ FAIL
[12:17:02] [INFO]     🤖 glm-4-plus (t=0.70) via llm_provider.llamacpp…
[12:17:02] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.70 max=4096 streaming…
[12:17:04] [INFO]     🤖 glm-4-plus (t=0.70) via llm_provider.llamacpp…
[12:17:04] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.70 max=4096 streaming…
[12:17:08] [INFO]     🤖 glm-4-plus (t=0.70) via llm_provider.llamacpp…
[12:17:08] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.70 max=4096 streaming…
[12:17:13] [INFO]     🤖 glm-4-plus (t=0.70) via llm_provider.llamacpp…
[12:17:13] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.70 max=4096 streaming…
[12:17:18] [INFO]     🤖 glm-4-plus (t=0.70) via llm_provider.llamacpp…
[12:17:18] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.70 max=4096 streaming…
[12:17:23] [INFO]     🤖 glm-4-plus (t=0.70) via llm_provider.llamacpp…
[12:17:23] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.70 max=4096 streaming…
[12:17:28] [DEBUG]     🔬 LLM grounding check: 6 call(s) for 59 bullets — 35 flagged ungrounded
[12:17:28] [DEBUG]     ℹ️ LLM flagged 'DSM-III-R (1987) revised the criteria fo…' as ungrounded, but source overlap is 100% — KEEPING (likely paraphrase)
[12:17:28] [DEBUG]     ℹ️ LLM flagged 'Schizotypal personality disorder emerged…' as ungrounded, but source overlap is 100% — KEEPING (likely paraphrase)
[12:17:28] [DEBUG]     ℹ️ LLM flagged 'Schizotypal personality disorder also em…' as ungrounded, but source overlap is 100% — KEEPING (likely paraphrase)
[12:17:28] [DEBUG]     ℹ️ LLM flagged 'Bleuler (1911) first described latent sc…' as ungrounded, but source overlap is 86% — KEEPING (likely paraphrase)
[12:17:28] [DEBUG]     ℹ️ LLM flagged 'Zilboorg (1941) and Hoch and Polatin (19…' as ungrounded, but source overlap is 100% — KEEPING (likely paraphrase)
[12:17:28] [DEBUG]     ℹ️ LLM flagged 'Rado (1953) hypothesized a constitutiona…' as ungrounded, but source overlap is 100% — KEEPING (likely paraphrase)
[12:17:28] [DEBUG]     ℹ️ LLM flagged 'Meehl (1962) provided a theoretical fram…' as ungrounded, but source overlap is 86% — KEEPING (likely paraphrase)
[12:17:28] [DEBUG]     ℹ️ LLM flagged 'Genetic studies by Kety et al. (1968, 19…' as ungrounded, but source overlap is 88% — KEEPING (likely paraphrase)
[12:17:28] [DEBUG]     ℹ️ LLM flagged 'DSM-III criteria for schizotypal persona…' as ungrounded, but source overlap is 100% — KEEPING (likely paraphrase)
[12:17:28] [DEBUG]     ℹ️ LLM flagged 'Subsequent research found social isolati…' as ungrounded, but source overlap is 89% — KEEPING (likely paraphrase)
[12:17:28] [DEBUG]     ℹ️ LLM flagged 'DSM-III-R expanded the criteria for schi…' as ungrounded, but source overlap is 86% — KEEPING (likely paraphrase)
[12:17:28] [DEBUG]     ℹ️ LLM flagged 'Including schizotypal disorder in person…' as ungrounded, but source overlap is 90% — KEEPING (likely paraphrase)
[12:17:28] [DEBUG]     ℹ️ LLM flagged 'Severe personality disorders frequently …' as ungrounded, but source overlap is 100% — KEEPING (likely paraphrase)
[12:17:28] [DEBUG]     ℹ️ LLM flagged 'Narcissistic and antisocial personality …' as ungrounded, but source overlap is 100% — KEEPING (likely paraphrase)
[12:17:28] [DEBUG]     ℹ️ LLM flagged 'Narcissistic individuals can achieve pro…' as ungrounded, but source overlap is 83% — KEEPING (likely paraphrase)
[12:17:28] [DEBUG]     ℹ️ LLM flagged 'Narcissistic symptomatology may shift in…' as ungrounded, but source overlap is 100% — KEEPING (likely paraphrase)
[12:17:28] [DEBUG]     ℹ️ LLM flagged 'Cultural influences shape the expression…' as ungrounded, but source overlap is 90% — KEEPING (likely paraphrase)
[12:17:28] [DEBUG]     ℹ️ LLM flagged 'Personality disorders exhibit phenotypic…' as ungrounded, but source overlap is 64% — KEEPING (likely paraphrase)
[12:17:28] [DEBUG]     ℹ️ LLM flagged 'Kernberg (1986) detailed differences bet…' as ungrounded, but source overlap is 100% — KEEPING (likely paraphrase)
[12:17:28] [DEBUG]     ℹ️ LLM flagged 'The author views histrionic disorder's s…' as ungrounded, but source overlap is 100% — KEEPING (likely paraphrase)
[12:17:28] [DEBUG]     ℹ️ LLM flagged 'The author argues hysterical personality…' as ungrounded, but source overlap is 80% — KEEPING (likely paraphrase)
[12:17:28] [DEBUG]     ℹ️ LLM flagged 'Histrionic individuals are easier to get…' as ungrounded, but source overlap is 100% — KEEPING (likely paraphrase)
[12:17:28] [DEBUG]     ℹ️ LLM flagged 'Histrionic individuals lack the sustaine…' as ungrounded, but source overlap is 88% — KEEPING (likely paraphrase)
[12:17:28] [DEBUG]     ℹ️ LLM flagged 'Bleuler (1908) coined "schizoid personal…' as ungrounded, but source overlap is 100% — KEEPING (likely paraphrase)
[12:17:28] [DEBUG]     ℹ️ LLM flagged 'Bleuler (1911) observed schizoid traits …' as ungrounded, but source overlap is 90% — KEEPING (likely paraphrase)
[12:17:28] [DEBUG]     ℹ️ LLM flagged 'Zilboorg (1941) described "ambulatory sc…' as ungrounded, but source overlap is 90% — KEEPING (likely paraphrase)
[12:17:28] [DEBUG]     ℹ️ LLM flagged 'Federn (1947) provided a less detailed d…' as ungrounded, but source overlap is 100% — KEEPING (likely paraphrase)
[12:17:28] [DEBUG]     ℹ️ LLM flagged 'Hoch and Polatin (1949) described "pseud…' as ungrounded, but source overlap is 100% — KEEPING (likely paraphrase)
[12:17:28] [DEBUG]     ℹ️ LLM flagged 'Rado (1953) hypothesized schizotypal ind…' as ungrounded, but source overlap is 100% — KEEPING (likely paraphrase)
[12:17:28] [DEBUG]     ℹ️ LLM flagged 'Meehl (1962) proposed an integrative neu…' as ungrounded, but source overlap is 100% — KEEPING (likely paraphrase)
[12:17:28] [DEBUG]     ℹ️ LLM flagged 'Kety et al. (1968, 1975) identified "bor…' as ungrounded, but source overlap is 89% — KEEPING (likely paraphrase)
[12:17:28] [DEBUG]     ℹ️ LLM flagged 'Spitzer et al. (1979) developed DSM-III …' as ungrounded, but source overlap is 100% — KEEPING (likely paraphrase)
[12:17:28] [DEBUG]     ℹ️ LLM flagged 'Post-DSM-III studies found social isolat…' as ungrounded, but source overlap is 100% — KEEPING (likely paraphrase)
[12:17:28] [DEBUG]     ℹ️ LLM flagged 'McGlashan (1987) reported odd communicat…' as ungrounded, but source overlap is 100% — KEEPING (likely paraphrase)
[12:17:28] [DEBUG]     ℹ️ LLM flagged 'DSM-III-R revised schizotypal criteria b…' as ungrounded, but source overlap is 78% — KEEPING (likely paraphrase)
[12:17:28] [INFO]     ⚖️ Judge appeal: KEPT 35 of 35 flagged bullet(s) — source overlap ≥ 0.25 to source
[12:17:28] [DEBUG]   ℹ️ Source grounding DISABLED — LLM-as-judge grounding check passed all 59 bullets.
[12:17:28] [INFO]   ℹ️ Summary has substantial content (exec=1399 chars, thorough=7513 chars) — Judge grounding check at 100% ungrounded is likely a false positive for this source length. Auto-passing to preserve content.
[12:17:28] [DEBUG]   ♻️  Recovery pass: no bullets eligible for recovery (threshold 30%).
[12:17:28] [INFO]     🎓 Running scholar reflection (gap analysis + gap-fill)…
[12:17:28] [DEBUG]     🎓 Theorist coverage check: 25 named author(s) found in source — verifying each is covered
[12:17:28] [INFO]     🤖 glm-4-plus (t=0.70) via llm_provider.llamacpp…
[12:17:28] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.70 max=6144 streaming…
[12:17:58] [INFO]     🎓 Gap-fill: added 12 new bullet(s) from scholar reflection (source-grounded)
[12:17:58] [INFO]     🎓 Scholar reflection: identified 8 gap(s), filled 12 with new bullets
[12:17:58] [DEBUG]     🎓 V18.2: Scholar reflections text suppressed (gap-fill only)
[12:17:58] [DEBUG]     🛡️ Anti-false-precision: no false-precision patterns found (0 rewrites)
[12:17:58] [DEBUG]     🧹 Semantic dedup: sentence-transformers not available — skipping
[12:17:58] [DEBUG]     🧹 V16.0.2 Bullet normalization: 71 bullets normalized
[12:17:58] [DEBUG]     [V17.5] Searching for analysis files in: /home/z/elixir/runs/ch9_v0519_1
[12:17:58] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS_analysis.md']
[12:17:58] [DEBUG]     [V17.5] Using analysis: 001_9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS_analysis.md (3911 chars), segment: 001_9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS.md
[12:17:58] [INFO]     🔧 Bullet consolidation SKIPPED — deterministic probe found 0 mergeable pairs (71 bullets, LLM call not needed; rig .3.7-.3.9: the LLM merged 0 on the same input shape)
[12:17:58] [DEBUG]     [V17.5] Searching for analysis files in: /home/z/elixir/runs/ch9_v0519_1
[12:17:58] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS_analysis.md']
[12:17:58] [DEBUG]     [V17.5] Using analysis: 001_9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS_analysis.md (3911 chars), segment: 001_9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS.md
[12:17:58] [INFO]     📊 V18.14 Bullets-only judge: ['Kernberg', 'Akhtar', 'Zetzel', 'Lesser', 'Tupin', 'Kety', 'Freud', 'Easser and Lesser', 'Bleuler', 'Rado', 'Spitzer', 'Easser', 'Wittels', 'Reich', 'Marmor', 'Blacker and Tupin', 'Meehl', 'Blacker', 'Fenichel', 'Halleck', 'Cooper', 'Abse', 'Lazare', 'Hoch', 'Klein', 'Hollender', 'Liebowitz and Klein', 'Zilboorg', 'Federn', 'Hoch and Polatin', 'McGlashan', 'Liebowitz', 'Polatin']/73 authors in bullets (45%) — MISSING from bullets: ['Gunderson', 'Siever', 'Kendler', 'Wolman', 'Bursten']
[12:17:58] [WARNING]     📊 V18.14 Thorough-only judge: ['Kernberg', 'Akhtar', 'Zetzel', 'Lesser', 'Tupin', 'Kety', 'Gunderson', 'Freud', 'Easser and Lesser', 'Bleuler', 'Rado', 'Spitzer', 'Easser', 'Wittels', 'Reich', 'Marmor', 'Blacker and Tupin', 'Meehl', 'Blacker', 'Fenichel', 'Halleck', 'Cooper', 'Abse', 'Siever', 'Kendler', 'Hoch', 'Klein', 'Lilienfeld', 'Liebowitz and Klein', 'Zilboorg', 'Hoch and Polatin', 'McGlashan', 'Liebowitz', 'Polatin']/73 authors in thorough (47%) — MISSING from thorough: ['Wolman', 'Lazare', 'Bursten', 'Akiskal', 'Bergman']
[12:17:58] [INFO]     🔍 V18.14.1: Batch gap-fill round 1: filling 8 missing authors: ['Gunderson', 'Siever', 'Kendler', 'Wolman', 'Bursten']…
[12:17:58] [INFO]     🤖 glm-4-plus (t=0.70) via llm_provider.llamacpp…
[12:17:58] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.70 max=2000 streaming…
[12:18:01] [INFO]     ✅ V18.14.1: Batch gap-fill round 1 added 8/8 bullets
[12:18:01] [DEBUG]     📊 V18.20.3.7: round 1 telemetry (3.2s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=0, added=8
[12:18:01] [DEBUG]     📊 V18.14.1: After round 1, 30 still missing from bullets: ['Robins', 'Rosenthal', 'Wender', 'Abraham', 'Kretschmer']…
[12:18:01] [INFO]     🔍 V18.14.1: Batch gap-fill round 2: filling 8 missing authors: ['Robins', 'Rosenthal', 'Wender', 'Abraham', 'Kretschmer']…
[12:18:01] [INFO]     🤖 glm-4-plus (t=0.70) via llm_provider.llamacpp…
[12:18:01] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.70 max=2000 streaming…
[12:18:04] [INFO]     ✅ V18.14.1: Batch gap-fill round 2 added 8/8 bullets
[12:18:04] [DEBUG]     📊 V18.20.3.7: round 2 telemetry (3.5s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=0, added=8
[12:18:04] [DEBUG]     📊 V18.14.1: After round 2, 18 still missing from bullets: ['Nanarello', 'Frances', 'Fairbairn', 'Guntrip', 'Ekstein']…
[12:18:04] [INFO]     🔍 V18.14.1: Batch gap-fill round 3: filling 8 missing authors: ['Nanarello', 'Frances', 'Fairbairn', 'Guntrip', 'Ekstein']…
[12:18:04] [INFO]     🤖 glm-4-plus (t=0.70) via llm_provider.llamacpp…
[12:18:04] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.70 max=2000 streaming…
[12:18:10] [INFO]     ✅ V18.14.1: Batch gap-fill round 3 added 8/8 bullets
[12:18:10] [DEBUG]     📊 V18.20.3.7: round 3 telemetry (5.1s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=0, added=8
[12:18:10] [DEBUG]     📊 V18.14.1: After round 3, 10 still missing from bullets: ['Wolf', 'Thomson', 'Erikson', 'Chick', 'Rinsley']…
[12:18:10] [INFO]     🔍 V18.14.1: Batch gap-fill round 4: filling 8 missing authors: ['Wolf', 'Thomson', 'Erikson', 'Chick', 'Rinsley']…
[12:18:10] [INFO]     🤖 glm-4-plus (t=0.70) via llm_provider.llamacpp…
[12:18:10] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.70 max=2000 streaming…
[12:18:16] [DEBUG]     🧹 Filtered 1 thinking + 0 narrative bullets + 0 truncated (kept 0)
[12:18:16] [INFO]     📋 Quarantine: 1 bullet drop(s) recorded. Stages: {'thinking_filter.truncated': 1}
[12:18:16] [DEBUG]     🎓 V18.12.2: Dropped gap-fill bullet (prompt-leakage/thinking): - Thomson: Cited alongside Akhtar in research indicating tha…
[12:18:16] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Rinsley: Cited for work on borderline phenomena (Rinsley 1980), which …
[12:18:16] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Bleiberg: Cited for work on narcissistic phenomena (Bleiberg 1984), wh…
[12:18:16] [DEBUG]     🧹 Filtered 1 thinking + 0 narrative bullets + 0 truncated (kept 0)
[12:18:16] [INFO]     📋 Quarantine: 2 bullet drop(s) recorded. Stages: {'thinking_filter.truncated': 2}
[12:18:16] [DEBUG]     🎓 V18.12.2: Dropped gap-fill bullet (prompt-leakage/thinking): - Snyder: Cited for describing how borderline individuals ma…
[12:18:16] [INFO]     ✅ V18.14.1: Batch gap-fill round 4 added 4/8 bullets
[12:18:16] [DEBUG]     📊 V18.20.3.7: round 4 telemetry (6.8s): response=8 bullet lines, dup=0, think-filtered=2, vetoed=0, filler=2, added=4
[12:18:16] [DEBUG]     📊 V18.14.1: After round 4, 5 still missing from bullets: ['Thomson', 'Rinsley', 'Bleiberg', 'Snyder', 'Widiger']
[12:18:16] [INFO]     🔍 V18.14.1: Batch gap-fill round 5: filling 5 missing authors: ['Thomson', 'Rinsley', 'Bleiberg', 'Snyder', 'Widiger']
[12:18:16] [INFO]     🤖 glm-4-plus (t=0.70) via llm_provider.llamacpp…
[12:18:16] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.70 max=2000 streaming…
[12:18:19] [INFO]     ✅ V18.14.1: Batch gap-fill round 5 added 5/5 bullets
[12:18:19] [DEBUG]     📊 V18.20.3.7: round 5 telemetry (2.6s): response=5 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=0, added=5
[12:18:19] [INFO]     ✅ V18.14.1: Batch gap-fill complete — added 33 bullets across 5 round(s)
[12:18:19] [DEBUG]     📝 V18.2.18: Lists & Frameworks section skipped (set summarisation.inject_lists_section=true to enable)
[12:18:19] [INFO]     ✅ V18.15.9.1: Added 1 consolidated Characteristics bullet (all 5 items, verbatim from source) — not scattered
[12:18:19] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 7-item runin_arabic list (3 item(s) were uncovered; all 7 now carried verbatim)
[12:18:19] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 6-item runin_arabic list (1 item(s) were uncovered; all 6 now carried verbatim)
[12:18:19] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 3-item runin_arabic list (2 item(s) were uncovered; all 3 now carried verbatim)
[12:18:19] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 5-item runin_arabic list (2 item(s) were uncovered; all 5 now carried verbatim)
[12:18:19] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 5-item roman_lower_paren list (4 item(s) were uncovered; all 5 now carried verbatim)
[12:18:19] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 3-item roman_lower_paren list (1 item(s) were uncovered; all 3 now carried verbatim)
[12:18:19] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item roman_lower_paren list (2 item(s) were uncovered; all 4 now carried verbatim)
[12:18:19] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 3-item runin_roman list (1 item(s) were uncovered; all 3 now carried verbatim)
[12:18:19] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 8-item runin_arabic list (3 item(s) were uncovered; all 8 now carried verbatim)
[12:18:19] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 6-item runin_arabic list (2 item(s) were uncovered; all 6 now carried verbatim)
[12:18:19] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item runin_arabic list (2 item(s) were uncovered; all 4 now carried verbatim)
[12:18:19] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 8-item runin_arabic list (1 item(s) were uncovered; all 8 now carried verbatim)
[12:18:19] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 3-item roman_lower_paren list (1 item(s) were uncovered; all 3 now carried verbatim)
[12:18:19] [DEBUG]     🧹 Semantic dedup: sentence-transformers not available — skipping
[12:18:19] [DEBUG]     [V17.5] Searching for analysis files in: /home/z/elixir/runs/ch9_v0519_1
[12:18:19] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS_analysis.md']
[12:18:19] [DEBUG]     [V17.5] Using analysis: 001_9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS_analysis.md (3911 chars), segment: 001_9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS.md
[12:18:21] [INFO]     🛡️ V18.2.13 Post-checks: 29 fixed, 21 flagged (of 116 bullets + exec + thorough)
[12:18:21] [DEBUG]       [attribution/flag] bullet[15]: attribution mismatch: summary's claim about 'Zilboorg (1941)' has 27% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  Zilboorg (1941) and Hoch and P…
[12:18:21] [DEBUG]       [grammar/flag] bullet[26]: no main verb detected in first 40 words of 'Narcissistic symptomatology may shift in…' — the bullet may be grammatically broken (generation/formatting failure)  |  Narcissistic symptomatology ma…
[12:18:21] [DEBUG]       [parenthetical_promotion/flag] bullet[32]: V0.5.15: bullet for 'Reich' flagged as parenthetical promotion BUT KEPT — the author is in the regex extract_citations (the deterministic source roster). The regex IS the grounding.  |  Reich (1933) emphasized phallic-oedipal conflicts, associati
[12:18:21] [DEBUG]       [sentence_fusion/flag] bullet[33]: likely sentence-fusion garble: 'sexualizing' is not in the source or English lexicon; it starts with source-word 'sexual' + a 5-char suffix 'izing' that is itself a suffix of another source word (a dropped-prefix fusion — the model fused 'sexual' with a source word ending in 'izing' but dropped that word's prefix).  |  and repressed strivings, sexualizing nonsexual relations.
[12:18:21] [DEBUG]       [attribution/flag] bullet[54]: attribution mismatch: summary's claim about 'Kety et al (1968)' has 48% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  Kety et al. (1968, 1975) ident…
[12:18:21] [DEBUG]       [attribution/flag] bullet[67]: attribution mismatch: summary's claim about 'Akhtar (1988)' has 47% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  Akhtar (1988) advocates for hy…
[12:18:21] [DEBUG]       [attribution/flag] bullet[71]: attribution mismatch: summary's claim about 'Gunderson and Singer (1975)' has 47% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …a, Gunderson and Siever 1983, Gunderson and Singer 1975).
[12:18:21] [DEBUG]       [attribution/flag] bullet[79]: thin roster-gap-fill bullet shape (citation-only one-liner, no contribution carried) — quality signal for the audit (V0.5.19)  |  Robins: Contributed to literature on early antisocial person
[12:18:21] [DEBUG]       [year/flag] bullet[87]: author 'Bleuler' cited with 1953, but the source cites this author with ['1908', '1911'] — possible cross-field year contamination (V0.5.18 consistency check)  |  …chizoid personality following Bleuler (1953).
[12:18:21] [DEBUG]       [attribution/flag] bullet[88]: thin roster-gap-fill bullet shape (citation-only one-liner, no contribution carried) — quality signal for the audit (V0.5.19)  |  Frances: contributed to the controversy about whether the hi
[12:18:21] [DEBUG]       [attribution/flag] bullet[95]: thin roster-gap-fill bullet shape (citation-only one-liner, no contribution carried) — quality signal for the audit (V0.5.19)  |  Wolf: Cited in studies examining the overlap of narcissistic
[12:18:21] [DEBUG]       [attribution/flag] bullet[97]: thin roster-gap-fill bullet shape (citation-only one-liner, no contribution carried) — quality signal for the audit (V0.5.19)  |  Chick: Cited in Wolff and Chick 1980 in relation to literatu
[12:18:21] [DEBUG]       [scar_label_stub/fix] bullet[100]: dropped verbless label stub (no predicate, or ends with a bare colon introducing absent sub-content) — names a topic but carries no claim  |  Rinsley: Cited for work on borderline phenomena.
[12:18:21] [DEBUG]       [scar_label_stub/fix] bullet[101]: dropped verbless label stub (no predicate, or ends with a bare colon introducing absent sub-content) — names a topic but carries no claim  |  Bleiberg: Cited for work on narcissistic phenomena.
[12:18:21] [DEBUG]       [attribution/flag] bullet[104]: bold-name attribution mismatch: '**Characteristics**: (1) mixed forms; (2) level of social fun…' has 48% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  **Characteristics**: (1) mixed…
[12:18:21] [DEBUG]       [truncated/flag] bullet[113]: enumeration-guarantee bullet LOOKS truncated — EXEMPT from the truncation drop (V0.4.24): its items are verbatim source text, verifiable against the source; no postcheck may silently drop a guaranteed bullet  |  **Similar ideas voiced by Zilboorg (1941,** — 8 items from t
[12:18:21] [DEBUG]       [truncated/fix] key_distinctions: dropped truncated line in key_distinctions (unmatched quote/paren, dangling tail, or no terminal punctuation — an additive item missing its contrast half is noise)  |  Histrionic personality disorder vs. Hysterical personality d
[12:18:21] [DEBUG]       [truncated/fix] key_distinctions: dropped truncated line in key_distinctions (unmatched quote/paren, dangling tail, or no terminal punctuation — an additive item missing its contrast half is noise)  |  Hysterical personality vs. Hysteroid/Infantile personality
[12:18:21] [DEBUG]       [truncated/fix] key_distinctions: dropped truncated line in key_distinctions (unmatched quote/paren, dangling tail, or no terminal punctuation — an additive item missing its contrast half is noise)  |  Hysterical personality vs. Infantile personality
[12:18:21] [DEBUG]       [truncated/fix] key_distinctions: dropped truncated line in key_distinctions (unmatched quote/paren, dangling tail, or no terminal punctuation — an additive item missing its contrast half is noise)  |  Genital or mature hysterical personality organization vs. In
[12:18:21] [DEBUG]       [truncated/fix] key_distinctions: dropped truncated line in key_distinctions (unmatched quote/paren, dangling tail, or no terminal punctuation — an additive item missing its contrast half is noise)  |  Schizotypal personality disorder vs. Latent schizophrenia
[12:18:21] [DEBUG]       [truncated/fix] key_distinctions: dropped truncated line in key_distinctions (unmatched quote/paren, dangling tail, or no terminal punctuation — an additive item missing its contrast half is noise)  |  Schizotypal personality disorder vs. Borderline personality 
[12:18:21] [DEBUG]       [truncated/fix] key_distinctions: dropped truncated line in key_distinctions (unmatched quote/paren, dangling tail, or no terminal punctuation — an additive item missing its contrast half is noise)  |  Schizoid personality vs. Schizotypal personality
[12:18:21] [DEBUG]       [quote_verification/fix] bullet[5]: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   from the more disturbed 
[12:18:21] [DEBUG]       [quote_verification/fix] bullet[6]: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   variant exhibits greater ego weakness, impulsivity, and reg
[12:18:21] [DEBUG]       [quote_verification/fix] bullet[60]: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   pathology to ego deficits: 
[12:18:21] [DEBUG]       [quote_verification/fix] bullet[65]: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |  multiple neurotic symptoms... much free-floating anxiety... 
[12:18:21] [DEBUG]       [quote_verification/fix] exec: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   from a more disturbed 
[12:18:21] [DEBUG]       [quote_verification/fix] exec: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   variant characterized by greater ego weakness. The chapter 
[12:18:21] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   from a more disturbed 
[12:18:21] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   variant characterized by greater ego weakness. The chapter 
[12:18:21] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   alongside the work of Wittels (1930), Marmor (1953), and Ha
[12:18:21] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |  —characterized by labile emotionality, active engagement wit
[12:18:21] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   The latter, originating from broken families with inadequat
[12:18:21] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   personality from a hysterical one, noting differences in th
[12:18:21] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |  ) showing significant developmental failure in basic ego fun
[12:18:21] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   but its criteria were criticized for representing only the 
[12:18:21] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   personality, characterized by identity diffusion, generaliz
[12:18:21] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   to describe a morbidly exaggerated inner life at the expens
[12:18:21] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   a form containing all core symptoms of schizophrenia in att
[12:18:21] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   and by Hoch and Polatin (1949) with 
[12:18:21] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   characterized by multiple neurotic symptoms, anxiety, and p
[12:18:21] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |  ) involving deficits in integrating pleasurable experiences 
[12:18:21] [DEBUG]       [near_duplicate/flag] bullet[75]: near-duplicate KEPT — uniquely covers source author(s) Bursten absent from the rest of the summary (the V0.5.17 author-coverage veto)  |  Bursten: Noted the overlap of narcissistic and paranoid pers
[12:18:21] [DEBUG]       [near_duplicate/flag] bullet[81]: near-duplicate KEPT — uniquely covers source author(s) Wender absent from the rest of the summary (the V0.5.17 author-coverage veto)  |  Wender: Collaborated on Danish adoptive studies.
[12:18:21] [DEBUG]       [near_duplicate/flag] bullet[84]: near-duplicate KEPT — uniquely covers source author(s) Rosen, Kasanin absent from the rest of the summary (the V0.5.17 author-coverage veto)  |  Kasanin and Rosen: Made significant contributions to the des
[12:18:21] [DEBUG]       [near_duplicate/flag] bullet[85]: near-duplicate KEPT — uniquely covers source author(s) Rennie, Terry absent from the rest of the summary (the V0.5.17 author-coverage veto)  |  Terry and Rennie: Made significant contributions to the desc
[12:18:21] [DEBUG]       [near_duplicate/flag] bullet[86]: near-duplicate KEPT — uniquely covers source author(s) Kallman absent from the rest of the summary (the V0.5.17 author-coverage veto)  |  Kallman: Made significant contributions to the description o
[12:18:21] [DEBUG]       [near_duplicate/flag] bullet[90]: near-duplicate KEPT — uniquely covers source author(s) Guntrip absent from the rest of the summary (the V0.5.17 author-coverage veto)  |  Guntrip: provided an astute understanding of the intrapsychi
[12:18:21] [DEBUG]       [near_duplicate/flag] bullet[95]: near-duplicate KEPT — uniquely covers source author(s) Wolf absent from the rest of the summary (the V0.5.17 author-coverage veto)  |  Wolf: Cited in studies examining the overlap of narcissistic
[12:18:21] [INFO]     ℹ️ V0.4.23: 116 bullets ship (>80 — the historical hard cap is REMOVED per the user's no-limit directive; dedup/consolidation/filler-floor are the reducers, never truncation).
[12:18:21] [WARNING]     🎯 V18.20.3.13 Thorough theorist floor: 34/73 authors in thorough — MISSING from thorough: ['Wolman', 'Lazare', 'Bursten', 'Akiskal', 'Bergman']
[12:18:21] [INFO]     🤖 glm-4-plus (t=0.70) via llm_provider.llamacpp…
[12:18:21] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.70 max=1536 streaming…
[12:18:27] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "The conceptual evolution of schizotypal personality disorder was furth…" — its name(s) never co-occur with the claim's key phrases in the source
[12:18:27] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Robins, in epidemiological contexts, and Wolman, in conceptual critiqu…" — its name(s) never co-occur with the claim's key phrases in the source
[12:18:27] [INFO]   ✨ V0.5.15: recovered 2 gap-fill sentence(s) whose authors are in the regex extract_citations (the attribution-edge dropped them but the regex IS the grounding)
[12:18:27] [INFO]     🤖 glm-4-plus (t=0.70) via llm_provider.llamacpp…
[12:18:27] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.70 max=1536 streaming…
[12:18:33] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Singer, alongside Gunderson, played a pivotal role in refining the dia…" — its name(s) never co-occur with the claim's key phrases in the source
[12:18:33] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Kraepelin’s early work on dementia praecox also laid historical ground…" — its name(s) never co-occur with the claim's key phrases in the source
[12:18:33] [INFO]   ✨ V0.5.15: recovered 3 gap-fill sentence(s) whose authors are in the regex extract_citations (the attribution-edge dropped them but the regex IS the grounding)
[12:18:33] [INFO]     🤖 glm-4-plus (t=0.70) via llm_provider.llamacpp…
[12:18:33] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.70 max=1536 streaming…
[12:18:39] [INFO]   ✨ V0.5.15: recovered 9 gap-fill sentence(s) whose authors are in the regex extract_citations (the attribution-edge dropped them but the regex IS the grounding)
[12:18:39] [INFO]     ✅ V18.20.3.13 Thorough gap-fill: floor 34/73 → 63/73 (3 chunked call(s), ≤12 names each; 3 name(s) beyond the 3-call bound remain thorough-uncovered — carried by the bullets/recall floor)
[12:18:39] [INFO]     📏 V18.20.3.4: Deterministic recall floor (final set): theorists 71/73 in final bullets (missing: ['Rinsley', 'Bleiberg']); conclusion items 5/5; enumerated items (all lists, whole chapter) 78/78. This regex-measured floor is the honest coverage number — the LLM judge's claim-recall measures a different thing and overstates content recall for long sources.
[12:18:39] [INFO]     📋 Quarantine: 2 bullet drop(s) recorded for this chapter → logs/drops.jsonl (NOT rendered in the delivered files).
[12:18:39] [DEBUG]   ⏱️ Chapter 1/1 took 245s (deadline 0s)
[12:18:39] [INFO] ✅ Chapter 1/1: 9 - HISTRIONIC AND SCHIZOTYPAL PERSONALI… complete
[12:18:39] [DEBUG] ELIXIR_PROGRESS {"done":1,"total":1,"bullets":116,"exec_chars":1395,"chapter_done":true}
[12:18:39] [DEBUG]   📊 Progress: 1/1 done | 116 bullets | 1,395 chars exec summary
[12:18:39] [INFO]   💾 Response cache: 0 hits / 0 misses (0% hit-rate), 0/1000 entries, 0 evictions
[12:18:39] [INFO]   🧮 Embedding cache: 0 hits / 0 misses (0% hit-rate), 2 entries
[12:18:39] [SUCCESS] 🏁 summarize_chapters done in 244.9s
[12:18:39] [INFO]   Result: success=True bullets=116 exec=1395ch thorough=11297ch in_tok=10732 out_tok=3265 glossary_names=73
[12:18:39] [INFO] 🛡️ V0.4.40 verification + polish LAYER (V0.5.6 glossary wiring)…
[12:18:39] [INFO]     ✨ V0.5.6 verification: [verification_coverage/flag] coverage-targeting (glossary-grounded): 2 source author(s) NOT found in the summary (Siever and Gunderson, Simic). Glossary: (none). Cross-ref: confirmed=58, llm_only=4, regex_only=15.
[12:18:44] [INFO]     ✨ V0.4.40 verification: applied 1 targeted correction(s) (0 via normalized anchor, 0 skipped) + 1 append(s) — polished output (35583 chars, 4 flags vs 4).
[12:18:44] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: summary date '1950' (ce:1950) NOT found in source — possible fabrication.
[12:18:44] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1924a' (ce:1924) NOT found in summary — possible omission.
[12:18:44] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1905' (ce:1905) NOT found in summary — possible omission.
[12:18:44] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1909' (ce:1909) NOT found in summary — possible omission.
[12:18:44] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1910' (ce:1910) NOT found in summary — possible omission.
[12:18:44] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1925' (ce:1925) NOT found in summary — possible omission.
[12:18:44] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1940s' (decade:1940) NOT found in summary — possible omission.
[12:18:44] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1950s' (decade:1950) NOT found in summary — possible omission.
[12:18:44] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1946' (ce:1946) NOT found in summary — possible omission.
[12:18:44] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1952' (ce:1952) NOT found in summary — possible omission.
[12:18:44] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1952' (ce:1952) NOT found in summary — possible omission.
[12:18:44] [WARNING]     ✨ V0.5.1 verification: [verification_coverage/flag] coverage-targeting (glossary-grounded): 2 source author(s) NOT found in the summary (Siever and Gunderson, Simic). Gloss
[12:18:44] [DEBUG]     ✨ V0.5.1 verification: [verification/fix] applied hallucination correction: 'Siever: Co-authored research with Gunderson compar' -> 'Siever: Co-authored research 
[12:18:44] [DEBUG]     ✨ V0.5.1 verification: [verification_append/fix] appended omission correction for author 'Simic' (append-mode, V0.5.19): 'Simic: Author of the poem "The Roach," which op
[12:18:44] [INFO]   Verification LAYER: 14 issues (fixes + flags)
[12:18:44] [INFO] 💾 Saved chapter summary: summaries/001_9_-_HISTRIONIC_AND_SCHIZOTYPAL_PERSONALITY_DISORDERS_v0.5.19.1_20260928-121429-8b2f3b9b_summary.md

Finished at: 2026-09-28T12:18:44.049658
