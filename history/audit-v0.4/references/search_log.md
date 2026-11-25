# 検索記録と新規性判定の範囲

検索日: 2026-11-26（Asia/Tokyo）。一次資料を優先。通常検索で発見し、強い検索と原著のopen/findで内容を確認した。最新の近接研究には2024–2026年の範囲を意識したrecency付き検索を含む。

## Root側の検索クエリ

- "emergent communication" "rate distortion" task
- "emergent communication" "catastrophic forgetting" continuous adaptation
- "emergent communication" "tool" "protocol" failure
- "Bridging semantics and pragmatics in information-theoretic emergent communication"
- "Trading off Utility, Informativeness, and Complexity in Emergent Communication"
- "Task-Based Information Compression" "Multi-Agent"
- "emergent communication" "tool" "failure" protocol evolution（recency 730日）
- "adaptive" "semantic" "communication" "risk" "continual"（recency 730日）
- "ToolDNA" "2026"（recency 730日）
- "ToolSandbox" stateful conversational tool use benchmark
- "tool" "failure recovery" "benchmark" agent language（recency 730日）
- "tool" "partial failure" "benchmark" agent（recency 730日）
- "Byte Latent Transformer" patches scale better than tokens
- "Dynamic Chunking" "Hierarchical Sequence Modeling"
- "Language Models" "Communication" "LMAC" "2026"（recency 730日）

## 確認範囲

比較CSVは22本。各行にmetadata_only / partial_fulltextと確認内容を記録した。特にHawkins 2020、Tucker 2022、Gualdoni 2024、2026 CoNLL/TACL、ToolDNAは方法・実験の該当本文を確認。LMACは原著掲載要旨と著者方法説明を中心に確認し、本文全体を読んだとは扱わない。

初回の関連研究担当メモは21本、統合時に統計方法のAgarwal 2021を加えて22本。Tucker 2022は環境を固定してtradeoff係数をannealする研究であり、環境側の帰結を変える提案と同一視しない。TACL研究はarXiv:2401.08461の2026改訂版まで確認。H-NetはarXiv初出2025とICLR2026掲載を区別した。

## 未取得・未確定の候補

- Failing Tools (OpenReview id j7YsSnA64D): 検索上の原著PDF候補は取得できたが、書誌・査読状態の確定ができず、forumアクセスはchallengeページ。主比較CSVに含めない。
- ParaRecover (arXiv:2609.12345という検索結果): 原著ページopenが失敗。検索スニペットの具体的な数値・採録情報を事実として使わない。
- その他の一次本文未取得候補は literature_novelty.md 末尾に列挙。未取得は研究が存在しない証拠ではない。

## 本調査の限界

系統的レビューではなく、先行との重複を検出し問いを絞るための重点的調査。全引用網・全投稿中論文・全ソースコードの再現は未実施。『世界初』『先行が一件もない』は主張しない。新規性の核心は、頻度固定の帰結変更、意味区分、actor-onlyとの因果比較、更新の実費を同じ識別設計で結び付ける点の候補である。最終の新規性主張は、投稿時点の更新検索と近接候補の精読を条件とする。

## 再利用時の注意

文献内容は当該著者の報告であり、本監査による実験再現ではない。提案との差分は監査者の推論。本文未読の手法詳細を補完していない。全文の再配布は行わず、正式URLと識別子を提供する。

