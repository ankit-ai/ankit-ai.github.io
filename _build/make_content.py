#!/usr/bin/env python3
"""
Merge the extraction workflow's output with the adversarial verify pass into
_build/content.json, the file the site generator reads.

Every abstract here was diffed word by word against the PDF by a second agent.
Every number was grep-confirmed to appear in the paper. Where verification
found a defect, the corrected value is used, not the original.
"""

import json
import os
import re

HARVEST = "/tmp/harvest.json"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "content.json")

h = json.load(open(HARVEST))
E = {x["slug"]: x for x in h["extract"]}
V = {x["slug"]: x for x in h["verify"]}

# Public-facing "What this paper does not show". Written from the verify pass and
# the extraction's own honesty notes. First person, because he is an author on all
# of these. Plain statements, no hedging, no defending.
HONESTY = {
 "apex-mem-agentic-semi-structured-memory":
  "Every accuracy number here comes from an LLM judge, not from human raters. "
  "Append-only storage is the paper's headline idea and we never ablated it directly, so the "
  "evidence for it is indirect. Full-context GPT-4o beats our GPT-4o configuration on LOCOMO, "
  "87.52 against 86.35, and adding search hurts temporal accuracy. On SealQA-Hard our 5.55 point "
  "margin is measured against O3, but the same table has GPT-5 with web search at 38.6, which "
  "makes the honest margin about 1.5 points. Table 1 and Table 3 also disagree on the Haiku "
  "overall score, 84.92 against 87.00, so quote the GPT-5 number and not that one.",

 "apex-em-procedural-episodic-experience-replay":
  "No human evaluation. The headline comparison against MemRL is not a controlled one, because "
  "each system runs on its own backbone; only 3 of 5 benchmarks get a same-backbone comparison, "
  "and where they do the margins are thin, plus 1.4 and plus 1.0 points on Lifelong and a tie at "
  "78.8 percent on the OS split. The 3.3 times MemRL figure depends on which no-memory baseline "
  "the delta uses, and the paper does not say; against GPT-4o's own no-memory row the multiple is "
  "closer to 2.2 times. The teacher judge makes code generation worse, not better, and costs about "
  "30 percent more compute. Cost and latency are estimated from list pricing, not measured.",

 "routed-graph-handoff":
  "This was accepted to EMNLP 2026, but the proceedings are not out yet, so this page cites the "
  "arXiv version, and the code has not been released. "
  "The 76 percent failure figure comes from an automated taxonomy, not human coding, spot-checked "
  "on 50 cases. The method wins on 2 of 4 benchmarks: BFCL is a tie, 75.4 against 75.3, and the "
  "AppWorld result is parity only because the router sends 89 percent of those tasks back to prose. "
  "Graph-only loses 14.6 points there on its own. Realized routing is coarse enough that it behaves "
  "close to a per-benchmark rule, and the oracle shows 8.6 points still unclaimed.",

 "cross-lingual-knowledge-distillation-answer-sentence-selection":
  "The paper says the method beats supervised fine-tuning for all target languages. That is too "
  "strong. German and Swahili are losses in the tables, and with the largest student trained on all "
  "languages on original TyDi-AS2 data it loses in five of seven. No student ever reaches the English "
  "teacher. Three seeds were run but only averages are reported, so the sub-point gaps are not shown "
  "to be real. Both datasets were built with Amazon Translate by a team that is mostly Amazon, so the "
  "machine-translation side is not vendor-neutral.",

 "wdrass-web-scale-document-retrieval-answer-sentence-selection":
  "The retrieval comparison against Natural Questions is measured only on our own test set, and the "
  "paper says why: that test set is not a random sample of NQ data. There is no reverse evaluation "
  "on NQ, and no comparison against BM25, ColBERT, or any dense retriever other than DPR. The gap "
  "also closes to about 2 points by K equals 5,000. Quote the tables rather than the prose: Section "
  "4.3 and Table 4 disagree on the accuracy gains, and the corpus size is stated four different ways "
  "across the paper.",

 "question-context-alignment-answer-sentence-selection":
  "There is no ablation anywhere in this paper, so the three components, the alignment, the sentence "
  "graph, and the mutual-information term, are never separated. The abstract claims state of the art "
  "on all benchmarks and that does not hold: our main model's WDRASS MAP falls below TANDA, 61.8 "
  "against 63.5, and the claim only works if the joint-reranking variant is counted. Three seeds, "
  "averages only, no significance tests. No latency measurement, which matters for a task that is "
  "latency-sensitive in production.",

 "efficient-fine-tuning-knowledge-aware-response-planning":
  "The paper never names the generative model it fine-tunes, and the three configurations in Table 3 "
  "are described only as different hyper-parameter settings with no values, so the generation results "
  "are not reproducible from the paper as written. There is no ablation separating the retriever from "
  "the two-step fine-tuning. The end-to-end table reports relative gains over TANDA with no absolute "
  "accuracy, no confidence intervals, and no annotator agreement. The method loses to TANDA on WDRASS "
  "MAP. The paper also contradicts itself about which configuration is best.",

 "controlled-text-generation-hidden-representation-transformations":
  "The abstract says seven baselines; the body compares against five plus base GPT-2. Everything runs "
  "on GPT-2 medium, 355M parameters, with nothing on larger or instruction-tuned models, and the "
  "attribute scorers are the same classifier families used to build the training data. Human "
  "evaluation is a real strength here, and it shows topicality is a statistical tie against all six "
  "baselines and that DExperts ties us on linguistic quality. Fluency regresses on sentiment "
  "steering. So \"outperforms all the baselines\" does not hold metric by metric.",

 "federated-learning-mixed-domain-translation":
  "Preliminary work, and the paper says so. One language direction, one aggregation rule, single runs, "
  "BLEU only, no human evaluation. The federated server loses to centralized data combination on "
  "OpenSubtitles, 19.17 against 21.82. Both bandwidth-saving variants cost quality, 32.28 and 24.49 "
  "average against 33.83. The main comparator is our own group's prior paper, sharing three authors, "
  "so the headline head-to-head is largely against ourselves. No ablation shows how much of the gain "
  "comes simply from starting every client at the strong WMT model.",

 "communication-efficient-federated-learning-nmt":
  "The Controller models lose to both comparators in our own tables, 29.46 BLEU against 33.83 for "
  "full-parameter federated training and 32.00 for centralized fine-tuning, so \"on par\" is generous. "
  "The roughly 6 times saving is a parameter count, not measured bytes on the wire or wall-clock time. "
  "No comparison against the standard communication-efficiency baselines such as sparsification or "
  "quantization, and the adapter comparison is qualitative with no numbers. Controllers are "
  "adapter-style layers under a new name, which the paper acknowledges.",

 "attribute-conditioning-multi-document-summarization":
  "Preprint, not peer reviewed, and its conclusion claims a new state of the art that no reviewer ever "
  "tested. No significance tests or seeds on any ROUGE number, so gains of 0.07 to 0.8 points cannot "
  "be separated from run-to-run noise. One dataset only. The human evaluation used 5 annotators over "
  "182 summaries and the 78 percent figure is raw agreement, not chance-corrected. Table 5's best "
  "single-component variant beats the full system on two of three metrics, which the paper does not "
  "explain. The acronym in the title has nothing to do with the ACM.",

 "dr-sas-deep-reinforced-self-attention-masks":
  "This started as a Stanford CS221 course project and was never peer reviewed. The gain is about one "
  "ROUGE point and the paper calls it marginal. Training was cut to 6 of 30 epochs at a quarter of the "
  "intended batch size, so the baseline is under-trained and 41.89 is not comparable to published "
  "CNN/DailyMail numbers. No human evaluation, no seeds, no significance tests. The claim that the "
  "summaries are more factual rests on two hand-picked articles with no factuality metric.",

 "bertqa-attention-on-steroids":
  "This is a Stanford CS224n course project report from March 2019, posted to arXiv nine months later. "
  "It is not a peer-reviewed paper and should not be read as one. Single runs on one dataset, no seeds "
  "or error bars, and no comparison against the 2019 leaders such as XLNet or RoBERTa. The conclusion "
  "claims a 3.5 point ensemble gain; the table shows 2.84. The headline test numbers are from the "
  "internal course leaderboard, not the public SQuAD 2.0 one. Answerable-question F1 never beats the "
  "baseline, so the gains come almost entirely from predicting \"no answer\" better.",
}


def topics_sentence(topics, title):
    """Turn the keyword list into a readable sentence. Sentence case, no Title Case,
    because Scholar can mistake Title Case headings for author names."""
    t = list(topics)
    body = ", ".join(t[:-1]) + ", and " + t[-1] if len(t) > 1 else t[0]
    return "This paper is about " + body + "."


def meta_desc(tldr):
    d = re.sub(r"\s+", " ", tldr).strip()
    if len(d) <= 300:
        return d
    return d[:297].rsplit(" ", 1)[0] + "..."


content = {}
applied = []

for slug, ex in E.items():
    v = V[slug]
    assert v["abstract_is_verbatim"], slug

    abstract = ex["abstract_verbatim"]
    if v.get("abstract_correction"):
        abstract = v["abstract_correction"]
        applied.append("%s: abstract replaced with verified text" % slug)

    results = ex["key_results"]
    if v.get("corrected_key_results"):
        results = v["corrected_key_results"]
        applied.append("%s: key results replaced with verified set (%d entries)"
                       % (slug, len(results)))
    drop = set(v.get("bad_result_indices") or [])
    if drop and not v.get("corrected_key_results"):
        results = [r for i, r in enumerate(results) if i not in drop]
        applied.append("%s: dropped result indices %s" % (slug, sorted(drop)))

    unver = set(v.get("unverified_numbers") or [])
    if unver:
        before = len(results)
        results = [r for r in results
                   if not any(u in r["text"] for u in unver)]
        applied.append("%s: dropped %d results carrying unverified numbers"
                       % (slug, before - len(results)))

    cap = ex["figure_caption_verbatim"]
    if v.get("figure_caption_correction"):
        cap = v["figure_caption_correction"]
        applied.append("%s: figure caption replaced with verified text" % slug)

    content[slug] = {
        "abstract": abstract,
        "abstract_word_count": len(abstract.split()),
        "tldr": ex["tldr"],
        "meta_description": meta_desc(ex["tldr"]),
        "why_it_matters": ex["why_it_matters"],
        "key_results": [{"text": r["text"],
                         "is_negative_or_null": bool(r.get("is_negative_or_null"))}
                        for r in results],
        "topics": ex["topics"],
        "topics_sentence": topics_sentence(ex["topics"], slug),
        "figure_caption": cap,
        "figure_alt": ex["figure_alt"],
        "bibtex": ex["bibtex"].strip(),
        "honesty_note": HONESTY[slug],
        "verification": {
            "verdict": v["overall_verdict"],
            "abstract_verbatim": True,
            "unverified_numbers": sorted(unver),
        },
    }

json.dump(content, open(OUT, "w"), indent=1, ensure_ascii=False, sort_keys=True)

print("wrote %s with %d papers" % (OUT, len(content)))
for a in applied:
    print("  applied " + a)
neg = sum(1 for c in content.values()
          for r in c["key_results"] if r["is_negative_or_null"])
print("  %d key results total, %d marked negative or null"
      % (sum(len(c["key_results"]) for c in content.values()), neg))
print("  abstract word counts: %s" % sorted(
    (c["abstract_word_count"], s) for s, c in content.items())[:3])
