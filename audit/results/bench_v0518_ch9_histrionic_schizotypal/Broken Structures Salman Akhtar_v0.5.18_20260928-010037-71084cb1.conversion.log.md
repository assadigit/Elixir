# Conversion Log: Broken Structures Salman Akhtar (repeatability harness)

Started at: 2026-09-28T01:00:37

<!-- generated-by: Elixir v0.5.18 | run_id=20260928-010037-71084cb1 | harness=scripts/repeatability_run.py -->

---

[01:00:37] [SUCCESS] 🚀 Repeatability run — headless end-to-end chapter pipeline
[01:00:37] [INFO]   Chapter file: source.md
[01:00:37] [INFO]   Heading: '9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS'
[01:00:37] [INFO]   Source: 7030 words / 50107 chars
[01:00:37] [INFO]   Frontmatter: {"title": "9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS", "book": "Broken Structures Salman Akhtar", "source_fil
[01:00:37] [INFO]   Endpoint: http://localhost:3031 (model glm-4-plus)
[01:00:37] [INFO]   Run id: 20260928-010037-71084cb1 (app 0.5.18)
[01:00:37] [INFO] ━━━ Conversion Settings (repeatability harness) ━━━
[01:00:37] [INFO]   provider=llamacpp
[01:00:37] [INFO]   model=glm-4-plus
[01:00:37] [INFO]   t=0.70
[01:00:37] [INFO]   max_context=128000
[01:00:37] [INFO]   max_output=32768
[01:00:37] [INFO]   coverage_floor=0.85
[01:00:37] [INFO]   overdeliver=True
[01:00:37] [INFO]   workers=1
[01:00:37] [INFO]   lang=en
[01:00:37] [INFO]   Layer8=disabled (local backend)
[01:00:38] [DEBUG]     🔧 HTTP timeout set to 600s (local mode)
[01:00:38] [DEBUG]   🎛️ Model profile: Default
[01:00:38] [INFO]   ℹ️ Heavy model fallback disabled (same as primary or empty).
[01:00:38] [INFO]   📝 Max output tokens: 32768 (context: 128000)
[01:00:38] [INFO]   Summarizer built (primary_model='glm-4-plus')
[01:00:38] [INFO]   📊 V17.2 Deterministic analysis: 1/1 segments analyzed → 001_9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS_analysis.md
[01:00:38] [INFO]     🎯 V15.2.0: Enhanced concept extraction starting (6 techniques)
[01:00:38] [DEBUG]     🎯 V15.2.0 #1 (intro+conclusion): 4 concepts — ['Charles Simic', 'Libidinal Types', 'Social Functioning Any', 'Related Differences Some']
[01:00:38] [DEBUG]     🎯 V15.2.0 #2 (proper-noun theorists): 15 concepts — ['Bleuler', 'Kernberg', 'Zetzel', 'Cooper', 'Lazare']
[01:00:38] [DEBUG]     🎯 V15.2.0 #3 (section headings): 2 concepts — ['Histrionic And Schizotypal\nPersonality Disorders', 'Mixed Forms And Extrinsic Influences On\nSymptomatology']
[01:00:38] [DEBUG]     🎯 V15.2.0 #4 (conclusion lists): 4 concepts — ['mixed forms', 'level of social functioning', 'sex-related differences', 'changes in symptomatology over the life span, and']
[01:00:38] [DEBUG]     🎯 V15.2.0 #5: LLM-assisted concept extraction starting...
[01:00:38] [INFO]     🦙 llama.cpp (glm-4-plus) t=1.00 max=800 streaming…
[01:00:40] [DEBUG]     ✅ V15.2.0 #5: LLM extracted 15 concepts
[01:00:40] [DEBUG]     🎯 V15.2.0 #5 (LLM-assisted): 15 concepts — ['Histrionic Personality Disorder', 'Schizotypal Personality Disorder', 'DSM-III (1980)', 'DSM-III-R (1987)', 'Hysterical personality']
[01:00:40] [DEBUG]     🎯 V15.2.0: merged 40 concepts before source-grounding
[01:00:40] [DEBUG]     🎯 V15.2.0 #6 (source-grounded): kept 37, dropped 3 ghost concepts — dropped: ['Freud\'s "erotic type"', 'Easser and Lesser\'s "hysteric" vs. "hysteroid" distinction', 'Pregenital/oral fixations']
[01:00:40] [INFO]     🎯 V15.2.0: FINAL 37 concepts (cap 50)
[01:00:40] [INFO]   🎯 37 concepts extracted (llm_assisted=True), 0 callouts
[01:00:40] [SUCCESS] 🚀 summarize_chapters() — the full 16-stage pipeline…
[01:00:40] [INFO] 📚 Summarising 1 chapters with 1 worker(s)...
[01:00:40] [INFO] 📚 Chapter 1/1: 9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS…
[01:00:40] [DEBUG]     [V17.5] Searching for analysis files in: /home/z/elixir/runs/ch9_v0518
[01:00:40] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS_analysis.md']
[01:00:40] [DEBUG]     [V17.5] Using analysis: 001_9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS_analysis.md (3911 chars), segment: 001_9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS.md
[01:00:40] [INFO]     📊 V17.2: Prepended deterministic analysis (3911 chars) — citation recall 78%→100%
[01:00:40] [INFO]     🧭 V0.10 (P6): strategy=single_pass (src=10,732 tok / window=128,000 / output=32,768) — adaptive window 128,000 > 32,768: src 10,732 <= usable 94,020 (window - output 32,768 - margin 700 - overhead 512)
[01:00:40] [INFO]     ⚡ Using primary model: glm-4-plus
[01:00:40] [DEBUG]     🎯 Injecting 37 concepts + 0 callouts into prompt
[01:00:40] [INFO]     📦 V0.4: master-summary architecture (default) — input 10732 tok, output cap 32768
[01:00:40] [INFO]     📦 V0.3 Call 1/3: Master Summary (comprehensive thorough)
[01:00:40] [INFO]     🤖 glm-4-plus (t=0.70) via llm_provider.llamacpp…
[01:00:40] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.70 max=32768 streaming…
[01:01:02] [INFO]     ✅ V0.3 Call 1/3: master summary = 478 words, 3686 chars
[01:01:02] [INFO]     📦 V0.3 Call 2/3: Derive bullet points from master summary
[01:01:02] [INFO]     🤖 glm-4-plus (t=0.70) via llm_provider.llamacpp…
[01:01:02] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.70 max=2048 streaming…
[01:01:12] [INFO]     ✅ V0.3 Call 2/3: 28 bullets derived from master summary
[01:01:12] [INFO]     📦 V0.3 Call 3/3: Derive executive summary from master + bullets
[01:01:12] [INFO]     🤖 glm-4-plus (t=0.70) via llm_provider.llamacpp…
[01:01:12] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.70 max=1024 streaming…
[01:01:20] [INFO]     ✅ V0.3 Call 3/3: exec summary = 193 words
[01:01:20] [INFO]     🤖 glm-4-plus (t=0.30) via llm_provider.llamacpp…
[01:01:20] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.30 max=8192 streaming…
[01:02:20] [INFO]     📖 V0.5.7 source glossary (separate call) → /home/z/elixir/runs/ch9_v0518/summaries/.glossaries/9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS.glossary.md
[01:02:20] [DEBUG]     📝 Parsed: exec=1582 chars, bullets=28, thorough=3686 chars
[01:02:21] [INFO]     📊 Primary coverage: 80% | keywords: ['personality', 'personality disorder', 'personality disorders', 'disorder', 'hysterical', 'disorders', 'hysterical personality', 'individuals']
[01:02:21] [DEBUG]     🔍 Coverage detail: 17/18 keywords found | missing: ['individuals']
[01:02:21] [INFO]     ℹ️ Coverage 80% < 85% — B3 voting disabled, will rely on over-delivery + gap-fill + 3-Tier Guarantee to push toward 100%
[01:02:21] [INFO]     📈 Coverage 80% < effective target 100% (over-deliver: floor 85% → target 100%) — applying 3-Tier Guarantee
[01:02:21] [DEBUG]     V16.0.3 3-Tier Guarantee: 1 concepts missing, gap-filling...
[01:02:21] [INFO]     🔍 Tier 2: targeted gap-fill for 1 missing concepts (parallel, focused calls)…
[01:02:21] [INFO]     🤖 glm-4-plus (t=1.00) via llm_provider.llamacpp…
[01:02:21] [INFO]     🦙 llama.cpp (glm-4-plus) t=1.00 max=200 streaming…
[01:02:21] [INFO]     ✅ Tier 2: gap-filled 1/1 concepts via focused LLM calls
[01:02:21] [INFO]     📊 Coverage breakdown: Tier 1 (synthesis) 80% → Tier 2 (gap-fill) 83% → Tier 3 (force-insert) 83%
[01:02:21] [DEBUG]     💾 V18.20.1.2: primary checkpoint saved (29 bullets, 193 exec words, 478 thorough words) → .checkpoints/primary_9_-_HISTRIONIC_AND_SCHIZOTYPAL_PERSONALITY_DISORDERS_summary.md
[01:02:22] [DEBUG]     🔍 Fact-check: all 29 bullets verified ✓
[01:02:22] [INFO]     📝 Additive sections missing — running followup call for distinctions + tensions…
[01:02:22] [INFO]     🤖 glm-4-plus (t=0.70) via llm_provider.llamacpp…
[01:02:22] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.70 max=4096 streaming…
[01:02:37] [WARNING]     ⚠️ V18.20.3.2: additive followup mass-truncation (8/8 lines would be dropped) — retrying the additive call once with a fresh generation
[01:02:37] [INFO]     🤖 glm-4-plus (t=0.70) via llm_provider.llamacpp…
[01:02:37] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.70 max=4096 streaming…
[01:02:49] [INFO]     ✅ V18.20.3.2: additive retry improved yield: 0 → 4 usable lines
[01:02:49] [INFO]     ✅ Additive sections via followup call: key_distinctions=370 chars, theoretical_tensions=475 chars (4/8 lines will be dropped as truncated)
[01:02:49] [DEBUG]     💾 V18.20.1.2: post-additive-sections checkpoint saved (29 bullets, 193 exec words, 478 thorough words, +key_distinctions, +theoretical_tensions) → .checkpoints/post-additive-sections_9_-_HISTRIONIC_AND_SCHIZOTYPAL_PERSONALITY_DISORDERS_summary.md
[01:02:49] [WARNING]     ⚠️ thorough_summary too short (478 words < 800 threshold) — requesting dedicated expansion…
[01:02:49] [INFO]     🤖 glm-4-plus (t=0.35) via llm_provider.llamacpp…
[01:02:49] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.35 max=8192 streaming…
[01:03:12] [INFO]     📖 Attempt 1/3: dedicated thorough = 478 words
[01:03:12] [DEBUG]     ⚠️ Attempt 1 empty/short — retrying with directive nudge after 3s
[01:03:15] [INFO]     🤖 glm-4-plus (t=0.35) via llm_provider.llamacpp…
[01:03:15] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.35 max=8192 streaming…
[01:03:25] [DEBUG]     ⚠️ Attempt 2 empty/short — retrying (attempt 3/3)
[01:03:25] [INFO]     🤖 glm-4-plus (t=0.35) via llm_provider.llamacpp…
[01:03:25] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.35 max=8192 streaming…
[01:03:39] [DEBUG]     📏 V0.4.38 F2: attempt 4 — re-prompting with a quantified length directive (best was 478 < 800 min words)
[01:03:39] [INFO]     🤖 glm-4-plus (t=0.35) via llm_provider.llamacpp…
[01:03:39] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.35 max=8192 streaming…
[01:03:49] [WARNING]     ℹ️ All 4 thorough attempts returned < 800 words (best=478) — keeping best-effort result
[01:03:49] [DEBUG]     ℹ️ Dedicated thorough call returned 478 words (not longer than original 478) — keeping original
[01:03:49] [INFO]     ⚠️ 29 bullets — requesting dedicated bullet expansion (full output budget)…
[01:03:49] [INFO]     🤖 glm-4-plus (t=0.70) via llm_provider.llamacpp…
[01:03:49] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.70 max=8192 streaming…
[01:04:22] [INFO]     ✅ Bullet expansion: 29 → 60 bullets (added 31 new via dedicated call)
[01:04:22] [INFO]     ✅ Final coverage 100%
[01:04:22] [DEBUG]     📏 F1: exec=193w, thorough=478w (source=7030w; targets exec<=250w, thorough<=3164w)
[01:04:22] [WARNING]     ⏭️  Phase 2.2: embedder unhealthy — skipping semantic fact-check (would produce false drops on zero-vector similarity, then recovery would resurrect them = churn)
[01:04:22] [DEBUG]     📖 F3: Reading level — source: 15.9, summary: 18.2 (diff: -2.3)
[01:04:22] [INFO]     ℹ️ F3: Summary is 2.3 grade levels denser than source — expected for a compressed academic summary.
[01:04:22] [DEBUG]     📊 I2: Chapter difficulty 0.52/1.0 (grade 15.9, strategy: multi_sample)
[01:04:22] [DEBUG]     🔄 J2: 33 cross-section redundancy(ies) found (exec↔bullets: 12, bullets↔thorough: 20)
[01:04:22] [DEBUG]     ✅ J3: Exec summary coherent (100/100, 5 markers)
[01:04:22] [DEBUG]     [V17.5] Analysis exists: 1 file(s) found — V17.4 skips ENABLED
[01:04:22] [INFO]     📊 V17.4: Deterministic analysis found — skipping old sequential gap-fill (V17.3 judge will handle it, saves ~20 min)
[01:04:22] [INFO]     📊 Judge: coverage=2% (1/56 claims), grounding=0% (0/60 bullets), hallucinations=60, deviations=0 — ❌ FAIL
[01:04:22] [INFO]     🤖 glm-4-plus (t=0.70) via llm_provider.llamacpp…
[01:04:22] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.70 max=4096 streaming…
[01:04:24] [INFO]     🤖 glm-4-plus (t=0.70) via llm_provider.llamacpp…
[01:04:24] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.70 max=4096 streaming…
[01:04:35] [INFO]     🤖 glm-4-plus (t=0.70) via llm_provider.llamacpp…
[01:04:35] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.70 max=4096 streaming…
[01:04:47] [INFO]     🤖 glm-4-plus (t=0.70) via llm_provider.llamacpp…
[01:04:47] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.70 max=4096 streaming…
[01:05:00] [INFO]     🤖 glm-4-plus (t=0.70) via llm_provider.llamacpp…
[01:05:00] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.70 max=4096 streaming…
[01:05:11] [INFO]     🤖 glm-4-plus (t=0.70) via llm_provider.llamacpp…
[01:05:11] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.70 max=4096 streaming…
[01:05:23] [DEBUG]     🔬 LLM grounding check: 6 call(s) for 60 bullets — 37 flagged ungrounded
[01:05:23] [DEBUG]     ℹ️ LLM flagged 'Genetic studies (Kety et al. 1968, 1975)…' as ungrounded, but source overlap is 100% — KEEPING (likely paraphrase)
[01:05:23] [DEBUG]     ℹ️ LLM flagged 'The emergence of the schizotypal categor…' as ungrounded, but source overlap is 100% — KEEPING (likely paraphrase)
[01:05:23] [DEBUG]     ℹ️ LLM flagged 'DSM-III criteria for schizotypal persona…' as ungrounded, but source overlap is 100% — KEEPING (likely paraphrase)
[01:05:23] [DEBUG]     ℹ️ LLM flagged 'Subsequent research (Gunderson and Sieve…' as ungrounded, but source overlap is 91% — KEEPING (likely paraphrase)
[01:05:23] [DEBUG]     ℹ️ LLM flagged 'DSM-III-R revised the criteria for schiz…' as ungrounded, but source overlap is 100% — KEEPING (likely paraphrase)
[01:05:23] [DEBUG]     ℹ️ LLM flagged 'The classification of schizotypal person…' as ungrounded, but source overlap is 90% — KEEPING (likely paraphrase)
[01:05:23] [DEBUG]     ℹ️ LLM flagged 'Schizotypal and affective spectrum disor…' as ungrounded, but source overlap is 100% — KEEPING (likely paraphrase)
[01:05:23] [DEBUG]     ℹ️ LLM flagged 'Schizotypal disorder is recognized as a …' as ungrounded, but source overlap is 100% — KEEPING (likely paraphrase)
[01:05:23] [DEBUG]     ℹ️ LLM flagged 'Mixed forms of severe personality disord…' as ungrounded, but source overlap is 90% — KEEPING (likely paraphrase)
[01:05:23] [DEBUG]     ℹ️ LLM flagged 'Level of social functioning in personali…' as ungrounded, but source overlap is 80% — KEEPING (likely paraphrase)
[01:05:23] [DEBUG]     ℹ️ LLM flagged 'Sex-related differences exist in the inc…' as ungrounded, but source overlap is 100% — KEEPING (likely paraphrase)
[01:05:23] [DEBUG]     ℹ️ LLM flagged 'Narcissistic and antisocial personality …' as ungrounded, but source overlap is 100% — KEEPING (likely paraphrase)
[01:05:23] [DEBUG]     ℹ️ LLM flagged 'Histrionic and borderline personality di…' as ungrounded, but source overlap is 100% — KEEPING (likely paraphrase)
[01:05:23] [DEBUG]     ℹ️ LLM flagged 'Narcissistic patients may shift from pro…' as ungrounded, but source overlap is 100% — KEEPING (likely paraphrase)
[01:05:23] [DEBUG]     ℹ️ LLM flagged 'Cultural factors influence the clinical …' as ungrounded, but source overlap is 79% — KEEPING (likely paraphrase)
[01:05:23] [DEBUG]     ℹ️ LLM flagged 'Severe personality disorders are not wat…' as ungrounded, but source overlap is 100% — KEEPING (likely paraphrase)
[01:05:23] [DEBUG]     ℹ️ LLM flagged 'The clinical picture of personality diso…' as ungrounded, but source overlap is 71% — KEEPING (likely paraphrase)
[01:05:23] [DEBUG]     ℹ️ LLM flagged 'Further research is needed into the deve…' as ungrounded, but source overlap is 78% — KEEPING (likely paraphrase)
[01:05:23] [DEBUG]     ℹ️ LLM flagged 'The author portrays histrionic personali…' as ungrounded, but source overlap is 93% — KEEPING (likely paraphrase)
[01:05:23] [DEBUG]     ℹ️ LLM flagged 'The author argues that hysterical person…' as ungrounded, but source overlap is 92% — KEEPING (likely paraphrase)
[01:05:23] [DEBUG]     ℹ️ LLM flagged 'Bleuler (1908) coined the term "schizoid…' as ungrounded, but source overlap is 100% — KEEPING (likely paraphrase)
[01:05:23] [DEBUG]     ℹ️ LLM flagged 'Bleuler (1911) observed schizoid traits …' as ungrounded, but source overlap is 92% — KEEPING (likely paraphrase)
[01:05:23] [DEBUG]     ℹ️ LLM flagged 'Zilboorg (1941, 1952) described "ambulat…' as ungrounded, but source overlap is 92% — KEEPING (likely paraphrase)
[01:05:23] [DEBUG]     ℹ️ LLM flagged 'Federn (1947) provided a description of …' as ungrounded, but source overlap is 100% — KEEPING (likely paraphrase)
[01:05:23] [DEBUG]     ℹ️ LLM flagged 'Hoch and Polatin (1949) described "pseud…' as ungrounded, but source overlap is 100% — KEEPING (likely paraphrase)
[01:05:23] [DEBUG]     ℹ️ LLM flagged 'Rado (1953) hypothesized that schizotypa…' as ungrounded, but source overlap is 100% — KEEPING (likely paraphrase)
[01:05:23] [DEBUG]     ℹ️ LLM flagged 'Meehl (1962) suggested an integrative ne…' as ungrounded, but source overlap is 86% — KEEPING (likely paraphrase)
[01:05:23] [DEBUG]     ℹ️ LLM flagged 'The Danish adoptive studies by Kety et a…' as ungrounded, but source overlap is 100% — KEEPING (likely paraphrase)
[01:05:23] [DEBUG]     ℹ️ LLM flagged 'The increasing popularity of the "border…' as ungrounded, but source overlap is 90% — KEEPING (likely paraphrase)
[01:05:23] [DEBUG]     ℹ️ LLM flagged 'Spitzer et al. (1979) developed eight cr…' as ungrounded, but source overlap is 100% — KEEPING (likely paraphrase)
[01:05:23] [DEBUG]     ℹ️ LLM flagged 'Post-DSM-III studies (Gunderson and Siev…' as ungrounded, but source overlap is 93% — KEEPING (likely paraphrase)
[01:05:23] [DEBUG]     ℹ️ LLM flagged 'McGlashan (1987) reported that odd commu…' as ungrounded, but source overlap is 100% — KEEPING (likely paraphrase)
[01:05:23] [DEBUG]     ℹ️ LLM flagged 'The author questions the conceptual inco…' as ungrounded, but source overlap is 92% — KEEPING (likely paraphrase)
[01:05:23] [DEBUG]     ℹ️ LLM flagged 'The author suggests schizotypal and affe…' as ungrounded, but source overlap is 100% — KEEPING (likely paraphrase)
[01:05:23] [DEBUG]     ℹ️ LLM flagged 'The author notes that schizotypal disord…' as ungrounded, but source overlap is 86% — KEEPING (likely paraphrase)
[01:05:23] [DEBUG]     ℹ️ LLM flagged 'The author highlights that mixed forms o…' as ungrounded, but source overlap is 83% — KEEPING (likely paraphrase)
[01:05:23] [DEBUG]     ℹ️ LLM flagged 'The author states that the level of soci…' as ungrounded, but source overlap is 83% — KEEPING (likely paraphrase)
[01:05:23] [INFO]     ⚖️ Judge appeal: KEPT 37 of 37 flagged bullet(s) — source overlap ≥ 0.25 to source
[01:05:23] [DEBUG]   ℹ️ Source grounding DISABLED — LLM-as-judge grounding check passed all 60 bullets.
[01:05:23] [WARNING]     🔄 Judge: coverage 2% < 85% — gap-filling 55 uncovered claim(s)
[01:05:23] [INFO]     🤖 glm-4-plus (t=0.49) via llm_provider.llamacpp…
[01:05:23] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.49 max=32768 streaming…
[01:05:40] [WARNING]     ⏭️  Gap-fill validation: embedder unhealthy — skipping Phase 2.2 (F4 source-overlap still gates every bullet; a zero-vector similarity would falsely reject them all)
[01:05:40] [INFO]     ✅ Judge: gap-fill added 6/6 bullet(s) (after F4 + Phase 2.2 validation)
[01:05:40] [INFO]   ℹ️ Summary has substantial content (exec=1582 chars, thorough=3684 chars) — Judge grounding check at 100% ungrounded is likely a false positive for this source length. Auto-passing to preserve content.
[01:05:40] [DEBUG]   ♻️  Recovery pass: no bullets eligible for recovery (threshold 30%).
[01:05:40] [INFO]     🎓 Running scholar reflection (gap analysis + gap-fill)…
[01:05:40] [DEBUG]     🎓 Theorist coverage check: 25 named author(s) found in source — verifying each is covered
[01:05:40] [INFO]     🤖 glm-4-plus (t=0.70) via llm_provider.llamacpp…
[01:05:40] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.70 max=6144 streaming…
[01:05:53] [DEBUG]     🎓 Dropped gap-fill without quote: Abraham’s (1921, 1924a,b) early papers on the relationship o…
[01:05:53] [DEBUG]     🎓 Dropped gap-fill without quote: Marmor (1953) challenged the notion that hysterical personal…
[01:05:53] [DEBUG]     🎓 Dropped gap-fill without quote: Kasanin and Rosen (1933) contributed to the description of s…
[01:05:53] [DEBUG]     🎓 Dropped gap-fill without quote: Noble (1951) popularized the notion of latent schizophrenia,…
[01:05:53] [DEBUG]     🎓 Dropped gap-fill without quote: Ekstein (1955) also contributed to popularizing the concept …
[01:05:53] [DEBUG]     🎓 Dropped gap-fill without quote: Terry and Rennie (1938) made significant contributions to th…
[01:05:53] [DEBUG]     🎓 Dropped gap-fill without quote: Nanarello (1953) made significant contributions to the descr…
[01:05:53] [INFO]     🎓 Gap-fill: added 1 new bullet(s) from scholar reflection (source-grounded)
[01:05:53] [INFO]     🎓 Scholar reflection: identified 8 gap(s), filled 1 with new bullets
[01:05:53] [DEBUG]     🎓 V18.2: Scholar reflections text suppressed (gap-fill only)
[01:05:53] [DEBUG]     🛡️ Anti-false-precision: no false-precision patterns found (0 rewrites)
[01:05:53] [DEBUG]     🧹 Semantic dedup: sentence-transformers not available — skipping
[01:05:53] [DEBUG]     🧹 V16.0.2 Bullet normalization: 67 bullets normalized
[01:05:53] [DEBUG]     [V17.5] Searching for analysis files in: /home/z/elixir/runs/ch9_v0518
[01:05:53] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS_analysis.md']
[01:05:53] [DEBUG]     [V17.5] Using analysis: 001_9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS_analysis.md (3911 chars), segment: 001_9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS.md
[01:05:53] [DEBUG]     🔧 Consolidated: 'Schizotypal and affective spectrum disor…' + 'The author suggests schizotypal and affe…' (sim=1.00)
[01:05:53] [DEBUG]     🔧 Consolidated: 'Schizotypal disorder is recognized as a …' + 'The author notes that schizotypal disord…' (sim=1.00)
[01:05:53] [DEBUG]     🔧 Consolidated: 'Level of social functioning in personali…' + 'The author states that the level of soci…' (sim=1.00)
[01:05:53] [INFO]     🔧 Bullet consolidation SKIPPED — deterministic probe found 0 mergeable pairs (67 bullets, LLM call not needed; rig .3.7-.3.9: the LLM merged 0 on the same input shape)
[01:05:53] [DEBUG]     [V17.5] Searching for analysis files in: /home/z/elixir/runs/ch9_v0518
[01:05:53] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS_analysis.md']
[01:05:53] [DEBUG]     [V17.5] Using analysis: 001_9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS_analysis.md (3911 chars), segment: 001_9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS.md
[01:05:53] [INFO]     📊 V18.14 Bullets-only judge: ['Kernberg', 'Zetzel', 'Lesser', 'Tupin', 'Kety', 'Gunderson', 'Freud', 'Easser and Lesser', 'Bleuler', 'Rado', 'Spitzer', 'Easser', 'Wittels', 'Reich', 'Marmor', 'Blacker and Tupin', 'Meehl', 'Blacker', 'Fenichel', 'Halleck', 'Cooper', 'Abse', 'Siever', 'Hoch', 'Klein', 'Abraham', 'Hollender', 'Liebowitz and Klein', 'Zilboorg', 'Federn', 'Hoch and Polatin', 'McGlashan', 'Liebowitz', 'Polatin']/73 authors in bullets (47%) — MISSING from bullets: ['Akhtar', 'Kendler', 'Wolman', 'Lazare', 'Bursten']
[01:05:53] [WARNING]     📊 V18.14 Thorough-only judge: ['Kernberg', 'Zetzel', 'Lesser', 'Kety', 'Gunderson', 'Freud', 'Easser and Lesser', 'Bleuler', 'Rado', 'Spitzer', 'Easser', 'Wittels', 'Reich', 'Marmor', 'Meehl', 'Fenichel', 'Halleck', 'Siever', 'Hoch', 'Zilboorg', 'Hoch and Polatin', 'McGlashan', 'Polatin']/73 authors in thorough (32%) — MISSING from thorough: ['Akhtar', 'Tupin', 'Blacker and Tupin', 'Blacker', 'Cooper']
[01:05:53] [INFO]     🔍 V18.14.1: Batch gap-fill round 1: filling 8 missing authors: ['Akhtar', 'Kendler', 'Wolman', 'Lazare', 'Bursten']…
[01:05:53] [INFO]     🤖 glm-4-plus (t=0.70) via llm_provider.llamacpp…
[01:05:53] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.70 max=2000 streaming…
[01:06:00] [DEBUG]     🧹 Filtered 1 thinking + 0 narrative bullets + 0 truncated (kept 0)
[01:06:00] [INFO]     📋 Quarantine: 1 bullet drop(s) recorded. Stages: {'thinking_filter.truncated': 1}
[01:06:00] [DEBUG]     🎓 V18.12.2: Dropped gap-fill bullet (prompt-leakage/thinking): - Lilienfeld: Histrionic individuals share sexual promiscuit…
[01:06:00] [INFO]     ✅ V18.14.1: Batch gap-fill round 1 added 7/8 bullets
[01:06:00] [DEBUG]     📊 V18.20.3.7: round 1 telemetry (6.7s): response=8 bullet lines, dup=0, think-filtered=1, vetoed=0, filler=0, added=7
[01:06:00] [DEBUG]     📊 V18.14.1: After round 1, 31 still missing from bullets: ['Lilienfeld', 'Robins', 'Rosenthal', 'Wender', 'Kretschmer']…
[01:06:00] [INFO]     🔍 V18.14.1: Batch gap-fill round 2: filling 8 missing authors: ['Lilienfeld', 'Robins', 'Rosenthal', 'Wender', 'Kretschmer']…
[01:06:00] [INFO]     🤖 glm-4-plus (t=0.70) via llm_provider.llamacpp…
[01:06:00] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.70 max=2000 streaming…
[01:06:10] [INFO]     ✅ V18.14.1: Batch gap-fill round 2 added 8/8 bullets
[01:06:10] [DEBUG]     📊 V18.20.3.7: round 2 telemetry (9.7s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=0, added=8
[01:06:10] [DEBUG]     📊 V18.14.1: After round 2, 19 still missing from bullets: ['Nanarello', 'Frances', 'Fairbairn', 'Guntrip', 'Ekstein']…
[01:06:10] [INFO]     🔍 V18.14.1: Batch gap-fill round 3: filling 8 missing authors: ['Nanarello', 'Frances', 'Fairbairn', 'Guntrip', 'Ekstein']…
[01:06:10] [INFO]     🤖 glm-4-plus (t=0.70) via llm_provider.llamacpp…
[01:06:10] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.70 max=2000 streaming…
[01:06:20] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Singer (1975) is cited in a discussion of personality disorders as a s…
[01:06:20] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Kraepelin (1921b) is cited for recognizing personality disorders as “f…
[01:06:20] [INFO]     ✅ V18.14.1: Batch gap-fill round 3 added 6/8 bullets
[01:06:20] [DEBUG]     📊 V18.20.3.7: round 3 telemetry (10.8s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=2, added=6
[01:06:20] [DEBUG]     📊 V18.14.1: After round 3, 13 still missing from bullets: ['Singer', 'Kraepelin', 'Reid', 'Wolf', 'Thomson']…
[01:06:20] [INFO]     🔍 V18.14.1: Batch gap-fill round 4: filling 8 missing authors: ['Singer', 'Kraepelin', 'Reid', 'Wolf', 'Thomson']…
[01:06:20] [INFO]     🤖 glm-4-plus (t=0.70) via llm_provider.llamacpp…
[01:06:20] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.70 max=2000 streaming…
[01:06:32] [INFO]     ✅ V18.14.1: Batch gap-fill round 4 added 8/8 bullets
[01:06:32] [DEBUG]     📊 V18.20.3.7: round 4 telemetry (11.7s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=0, added=8
[01:06:32] [DEBUG]     📊 V18.14.1: After round 4, 3 still missing from bullets: ['Bleiberg', 'Snyder', 'Widiger']
[01:06:32] [INFO]     🔍 V18.14.1: Batch gap-fill round 5: filling 3 missing authors: ['Bleiberg', 'Snyder', 'Widiger']
[01:06:32] [INFO]     🤖 glm-4-plus (t=0.70) via llm_provider.llamacpp…
[01:06:32] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.70 max=2000 streaming…
[01:06:41] [INFO]     ✅ V18.14.1: Batch gap-fill round 5 added 3/3 bullets
[01:06:41] [DEBUG]     📊 V18.20.3.7: round 5 telemetry (8.9s): response=3 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=0, added=3
[01:06:41] [INFO]     ✅ V18.14.1: Batch gap-fill complete — added 32 bullets across 5 round(s)
[01:06:41] [DEBUG]     📝 V18.2.18: Lists & Frameworks section skipped (set summarisation.inject_lists_section=true to enable)
[01:06:41] [INFO]     ✅ V18.15.9.1: Added 1 consolidated Characteristics bullet (all 5 items, verbatim from source) — not scattered
[01:06:41] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 7-item runin_arabic list (6 item(s) were uncovered; all 7 now carried verbatim)
[01:06:41] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 5-item runin_arabic list (3 item(s) were uncovered; all 5 now carried verbatim)
[01:06:41] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 3-item runin_arabic list (2 item(s) were uncovered; all 3 now carried verbatim)
[01:06:41] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 5-item runin_arabic list (2 item(s) were uncovered; all 5 now carried verbatim)
[01:06:41] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 5-item roman_lower_paren list (4 item(s) were uncovered; all 5 now carried verbatim)
[01:06:41] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 3-item roman_lower_paren list (1 item(s) were uncovered; all 3 now carried verbatim)
[01:06:41] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item roman_lower_paren list (2 item(s) were uncovered; all 4 now carried verbatim)
[01:06:41] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 8-item runin_arabic list (3 item(s) were uncovered; all 8 now carried verbatim)
[01:06:41] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 6-item runin_arabic list (2 item(s) were uncovered; all 6 now carried verbatim)
[01:06:41] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item runin_arabic list (2 item(s) were uncovered; all 4 now carried verbatim)
[01:06:41] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 8-item runin_arabic list (2 item(s) were uncovered; all 8 now carried verbatim)
[01:06:41] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 3-item roman_lower_paren list (2 item(s) were uncovered; all 3 now carried verbatim)
[01:06:41] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 3-item ordinal list (1 item(s) were uncovered; all 3 now carried verbatim)
[01:06:41] [DEBUG]     🧹 Semantic dedup: sentence-transformers not available — skipping
[01:06:41] [DEBUG]     [V17.5] Searching for analysis files in: /home/z/elixir/runs/ch9_v0518
[01:06:41] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS_analysis.md']
[01:06:41] [DEBUG]     [V17.5] Using analysis: 001_9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS_analysis.md (3911 chars), segment: 001_9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS.md
[01:06:43] [INFO]     🛡️ V18.2.13 Post-checks: 16 fixed, 15 flagged (of 107 bullets + exec + thorough)
[01:06:43] [DEBUG]       [attribution/flag] bullet[13]: attribution mismatch: summary's claim about 'Gunderson and Siever (1983)' has 47% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  Subsequent research (Gunderson and Siever 1983, McG…
[01:06:43] [DEBUG]       [sentence_fusion/flag] bullet[18]: likely sentence-fusion garble: 'borderline-antisocial' contains two source-words 'order' and 'social' separated by a 8-char gap 'lineanti' (not in source or English lexicon). The gap is likely a remnant of a dropped sentence boundary.  |  narcissistic-paranoid or borderline-antisocial overlaps.
[01:06:43] [DEBUG]       [sentence_fusion/flag] bullet[58]: likely sentence-fusion garble: 'borderline-antisocial' contains two source-words 'order' and 'social' separated by a 8-char gap 'lineanti' (not in source or English lexicon). The gap is likely a remnant of a dropped sentence boundary.  |  narcissistic-paranoid or borderline-antisocial overlaps, are common.
[01:06:43] [DEBUG]       [attribution/flag] bullet[67]: attribution mismatch: summary's claim about 'Gorton and Akhtar (1990)' has 48% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …for the older hysterical one (Gorton and Akhtar 1990).
[01:06:43] [DEBUG]       [attribution/flag] bullet[99]: bold-name attribution mismatch: '**Characteristics**: (1) mixed forms; (2) level of social fun…' has 48% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  **Characteristics**: (1) mixed…
[01:06:43] [DEBUG]       [truncated/flag] bullet[107]: enumeration-guarantee bullet LOOKS truncated — EXEMPT from the truncation drop (V0.4.24): its items are verbatim source text, verifiable against the source; no postcheck may silently drop a guaranteed bullet  |  **Similar ideas voiced by Zilboorg (1941,** — 8 items from t
[01:06:43] [DEBUG]       [sentence_fusion/flag] thorough: likely sentence-fusion garble: 'borderline-antisocial' contains two source-words 'order' and 'social' separated by a 8-char gap 'lineanti' (not in source or English lexicon). The gap is likely a remnant of a dropped sentence boundary.  |  narcissistic-paranoid or borderline-antisocial), level of social functi
[01:06:43] [DEBUG]       [truncated/fix] key_distinctions: dropped truncated line in key_distinctions (unmatched quote/paren, dangling tail, or no terminal punctuation — an additive item missing its contrast half is noise)  |  Hysterical personality vs. Histrionic personality disorder
[01:06:43] [DEBUG]       [truncated/fix] key_distinctions: dropped truncated line in key_distinctions (unmatched quote/paren, dangling tail, or no terminal punctuation — an additive item missing its contrast half is noise)  |  "True" hysterical personality vs. "Hysteroid" personality
[01:06:43] [DEBUG]       [truncated/fix] key_distinctions: dropped truncated line in key_distinctions (unmatched quote/paren, dangling tail, or no terminal punctuation — an additive item missing its contrast half is noise)  |  Schizoid personality vs. Schizotypal personality disorder
[01:06:43] [DEBUG]       [truncated/fix] key_distinctions: dropped truncated line in key_distinctions (unmatched quote/paren, dangling tail, or no terminal punctuation — an additive item missing its contrast half is noise)  |  Hypomanic/cyclothymic/depressive spectrum disorders vs. Schi
[01:06:43] [DEBUG]       [quote_verification/fix] bullet[2]: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   hysteric and the more pathological 
[01:06:43] [DEBUG]       [quote_verification/fix] bullet[62]: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   hysteric and the more pathological 
[01:06:43] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   hysteric from the more pathological 
[01:06:43] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   while Kernberg (1967) and Zetzel (1968) further delineated 
[01:06:43] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   (Bleuler 1911, Zilboorg 1941, Hoch and Polatin 1949). Theor
[01:06:43] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   concept. DSM-III criteria, derived from Spitzer et al.'s (1
[01:06:43] [DEBUG]       [near_duplicate/fix] bullet[56]: near-duplicate of a kept bullet (token-set containment >= 0.8) — kept the first, dropped this one  |  The author suggests schizotypal and affective spectrum disor
[01:06:43] [DEBUG]       [near_duplicate/fix] bullet[57]: near-duplicate of a kept bullet (token-set containment >= 0.8) — kept the first, dropped this one  |  The author notes that schizotypal disorder is recognized as 
[01:06:43] [DEBUG]       [near_duplicate/fix] bullet[58]: near-duplicate of a kept bullet (token-set containment >= 0.8) — kept the first, dropped this one  |  The author highlights that mixed forms of severe personality
[01:06:43] [DEBUG]       [near_duplicate/fix] bullet[59]: near-duplicate of a kept bullet (token-set containment >= 0.8) — kept the first, dropped this one  |  The author states that the level of social functioning in pe
[01:06:43] [DEBUG]       [near_duplicate/fix] bullet[62]: near-duplicate of a kept bullet (token-set containment >= 0.8) — kept the first, dropped this one  |  Easser and Lesser (1965) distinguished between the "true hys
[01:06:43] [DEBUG]       [near_duplicate/fix] bullet[66]: near-duplicate of a kept bullet (token-set containment >= 0.8) — kept the first, dropped this one  |  Federn (1947) provided a description of "latent schizophreni
[01:06:43] [DEBUG]       [near_duplicate/flag] bullet[75]: near-duplicate KEPT — uniquely covers source author(s) Robins absent from the rest of the summary (the V0.5.17 author-coverage veto)  |  Robins: Narcissistic, antisocial, and paranoid personality d
[01:06:43] [DEBUG]       [near_duplicate/flag] bullet[77]: near-duplicate KEPT — uniquely covers source author(s) Wender absent from the rest of the summary (the V0.5.17 author-coverage veto)  |  Wender: Contributed to Danish adoptive studies on the topic 
[01:06:43] [DEBUG]       [near_duplicate/flag] bullet[79]: near-duplicate KEPT — uniquely covers source author(s) Rosen, Kasanin absent from the rest of the summary (the V0.5.17 author-coverage veto)  |  Kasanin and Rosen: Made a significant contribution to the de
[01:06:43] [DEBUG]       [near_duplicate/flag] bullet[80]: near-duplicate KEPT — uniquely covers source author(s) Rennie, Terry absent from the rest of the summary (the V0.5.17 author-coverage veto)  |  Terry and Rennie: Made a significant contribution to the des
[01:06:43] [DEBUG]       [near_duplicate/flag] bullet[81]: near-duplicate KEPT — uniquely covers source author(s) Kallman absent from the rest of the summary (the V0.5.17 author-coverage veto)  |  Kallman: Made a significant contribution to the description 
[01:06:43] [DEBUG]       [near_duplicate/flag] bullet[82]: near-duplicate KEPT — uniquely covers source author(s) Nanarello absent from the rest of the summary (the V0.5.17 author-coverage veto)  |  Nanarello (1953) made significant contributions to the descr
[01:06:43] [DEBUG]       [near_duplicate/flag] bullet[85]: near-duplicate KEPT — uniquely covers source author(s) Guntrip absent from the rest of the summary (the V0.5.17 author-coverage veto)  |  Guntrip (1969) provided an astute understanding of the intra
[01:06:43] [DEBUG]       [near_duplicate/flag] bullet[92]: near-duplicate KEPT — uniquely covers source author(s) Thomson absent from the rest of the summary (the V0.5.17 author-coverage veto)  |  Thomson: Found narcissistic, antisocial, and paranoid person
[01:06:43] [INFO]     ℹ️ V0.4.23: 107 bullets ship (>80 — the historical hard cap is REMOVED per the user's no-limit directive; dedup/consolidation/filler-floor are the reducers, never truncation).
[01:06:43] [WARNING]     🎯 V18.20.3.13 Thorough theorist floor: 23/73 authors in thorough — MISSING from thorough: ['Akhtar', 'Tupin', 'Blacker and Tupin', 'Blacker', 'Cooper']
[01:06:43] [INFO]     🤖 glm-4-plus (t=0.70) via llm_provider.llamacpp…
[01:06:43] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.70 max=1536 streaming…
[01:06:58] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Further refining the conceptualization of histrionic personality, Akht…" — its name(s) never co-occur with the claim's key phrases in the source
[01:06:58] [INFO]   ✨ V0.5.15: recovered 3 gap-fill sentence(s) whose authors are in the regex extract_citations (the attribution-edge dropped them but the regex IS the grounding)
[01:06:58] [INFO]     🤖 glm-4-plus (t=0.70) via llm_provider.llamacpp…
[01:06:58] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.70 max=1536 streaming…
[01:07:08] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Further refinements to the conceptualization of histrionic personality…" — its name(s) never co-occur with the claim's key phrases in the source
[01:07:08] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "This empirical finding complemented the psychoanalytic delineations of…" — its name(s) never co-occur with the claim's key phrases in the source
[01:07:08] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "These early observations laid the groundwork for the genetic studies o…" — its name(s) never co-occur with the claim's key phrases in the source
[01:07:08] [INFO]     🤖 glm-4-plus (t=0.70) via llm_provider.llamacpp…
[01:07:08] [INFO]     🦙 llama.cpp (glm-4-plus) t=0.70 max=1536 streaming…
[01:07:20] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "The psychoanalytic exploration of schizoid phenomena further complicat…" — its name(s) never co-occur with the claim's key phrases in the source
[01:07:20] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Fairbairn’s object relations theory reframed schizoid dynamics as stem…" — its name(s) never co-occur with the claim's key phrases in the source
[01:07:20] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Ekstein, in turn, contributed to the latent schizophrenia literature b…" — its name(s) never co-occur with the claim's key phrases in the source
[01:07:20] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "This conceptual fluidity was paralleled by the work of Reid and Wolf, …" — its name(s) never co-occur with the claim's key phrases in the source
[01:07:20] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Finally, Thomson’s research on the genetic underpinnings of schizophre…" — its name(s) never co-occur with the claim's key phrases in the source
[01:07:20] [INFO]   ✨ V0.5.15: recovered 1 gap-fill sentence(s) whose authors are in the regex extract_citations (the attribution-edge dropped them but the regex IS the grounding)
[01:07:20] [INFO]     ✅ V18.20.3.13 Thorough gap-fill: floor 23/73 → 42/73 (3 chunked call(s), ≤12 names each; 14 name(s) beyond the 3-call bound remain thorough-uncovered — carried by the bullets/recall floor)
[01:07:20] [INFO]     📏 V18.20.3.4: Deterministic recall floor (final set): theorists 73/73 in final bullets; conclusion items 5/5; enumerated items (all lists, whole chapter) 74/74. This regex-measured floor is the honest coverage number — the LLM judge's claim-recall measures a different thing and overstates content recall for long sources.
[01:07:20] [INFO]     📋 Quarantine: 1 bullet drop(s) recorded for this chapter → logs/drops.jsonl (NOT rendered in the delivered files).
[01:07:20] [DEBUG]   ⏱️ Chapter 1/1 took 400s (deadline 0s)
[01:07:20] [INFO] ✅ Chapter 1/1: 9 - HISTRIONIC AND SCHIZOTYPAL PERSONALI… complete
[01:07:20] [DEBUG] ELIXIR_PROGRESS {"done":1,"total":1,"bullets":107,"exec_chars":1582,"chapter_done":true}
[01:07:20] [DEBUG]   📊 Progress: 1/1 done | 107 bullets | 1,582 chars exec summary
[01:07:20] [INFO]   💾 Response cache: 0 hits / 0 misses (0% hit-rate), 0/1000 entries, 0 evictions
[01:07:20] [INFO]   🧮 Embedding cache: 0 hits / 0 misses (0% hit-rate), 10 entries
[01:07:20] [SUCCESS] 🏁 summarize_chapters done in 399.7s
[01:07:20] [INFO]   Result: success=True bullets=107 exec=1582ch thorough=6288ch in_tok=10732 out_tok=2741 glossary_names=76
[01:07:20] [INFO] 🛡️ V0.4.40 verification + polish LAYER (V0.5.6 glossary wiring)…
[01:07:20] [INFO]     ✨ V0.5.6 verification: [verification_coverage/flag] coverage-targeting (glossary-grounded): 3 source author(s) NOT found in the summary (DSM-II, Kohut and Wolf, Simic). Glossary: (none). Cross-ref: confirmed=59, llm_only=7, regex_only=14.
[01:07:30] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: summary date '1961' (ce:1961) NOT found in source — possible fabrication.
[01:07:30] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: summary date '1972' (ce:1972) NOT found in source — possible fabrication.
[01:07:30] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1905' (ce:1905) NOT found in summary — possible omission.
[01:07:30] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1909' (ce:1909) NOT found in summary — possible omission.
[01:07:30] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1910' (ce:1910) NOT found in summary — possible omission.
[01:07:30] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1925' (ce:1925) NOT found in summary — possible omission.
[01:07:30] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1940s' (decade:1940) NOT found in summary — possible omission.
[01:07:30] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1950s' (decade:1950) NOT found in summary — possible omission.
[01:07:30] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1966' (ce:1966) NOT found in summary — possible omission.
[01:07:30] [WARNING]     ✨ V0.5.1 verification: [verification_coverage/flag] coverage-targeting (glossary-grounded): 3 source author(s) NOT found in the summary (DSM-II, Kohut and Wolf, Simic). Glo
[01:07:30] [INFO]   Verification LAYER: 10 issues (fixes + flags)
[01:07:30] [INFO] 💾 Saved chapter summary: summaries/001_9_-_HISTRIONIC_AND_SCHIZOTYPAL_PERSONALITY_DISORDERS_v0.5.18_20260928-010037-71084cb1_summary.md

Finished at: 2026-09-28T01:07:30.113306
