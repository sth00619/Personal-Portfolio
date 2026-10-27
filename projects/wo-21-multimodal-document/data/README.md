# FUNSD data

The downloader fetches the archive linked from the [official FUNSD project page](https://guillaumejaume.github.io/FUNSD/) and verifies SHA-256 `c31735649e4f441bcbb4fd0f379574f7520b42286e80b01d80b445649d54761f` before extracting it to `data/raw/`. The archive itself is excluded from Git.

The official page reports 199 forms, 31,485 words, 9,707 semantic entities, and 5,304 relations, with the 149/50 training/test split. The downloaded archive contains 149 training and 50 test annotations, and its OCR word records sum to 31,485. Counting each `form` record gives 9,743 entities; deduplicating all directed entity relation pairs by `(document, source_id, target_id)` gives 5,294. These differ from the page summary by 36 entities and 10 relations. The project task uses the question-to-answer subset: 3,129 train links and 837 test links. The downloader records the archive checksum and the code's direct parse counts instead of silently aligning them to the overview.

The project page links the 2019 paper but does not state a dataset redistribution license. The raw archive and document images are not committed. Review the source terms before redistributing copies or excerpts.

Run `docker compose run --build --rm download` from the project directory to download and verify the original data.
