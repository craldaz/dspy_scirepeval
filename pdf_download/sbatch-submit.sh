#! /bin/bash
for PART_FILE in ./split_cids/*; do
    OUTPUT_NAME=$(basename "$PART_FILE")
    echo "Submitting job for file $OUTPUT_NAME, the intput is $PART_FILE"
    sbatch sbatch-process-file.sh "$PART_FILE" "./split-near-papers-scincl-2447/$OUTPUT_NAME"
done
