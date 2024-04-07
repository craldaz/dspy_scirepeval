#!/bin/bash
#SBATCH -p express
#SBATCH -t 59

export JSALTdir=/work/k.church/JSALT-2023/
export JSALTsrc=/work/k.church/githubs/JSALT_Better_Together/src
export specter=$JSALTdir/semantic_scholar/embeddings/specter
export specter2=$JSALTdir/semantic_scholar/embeddings/specter2
export proposed=$JSALTdir/semantic_scholar/embeddings/proposed
export scincl=$JSALTdir/semantic_scholar/embeddings/scincl

module load python/3.8.1
source $HOME/venv/gft/bin/activate
module load jq
export gft=$HOME/public_github/gft
PATH=$PATH:$gft/gft:/work/k.church/githubs/zstd/programs
export gft_checkpoints=/work/k.church/gft/results/20220610
src=/work/k.church/semantic_scholar/citations/graphs/src
jobs=/work/k.church/semantic_scholar/jobs
PATH=$PATH:$HOME/final/suffix:$src:$src/C:$jobs:/work/k.church/sqlite/bld

INPUT_FILE=$1
OUTPUT_FILE=$2

# Due to a time limit on the cluster, I have to rerun the script. 
# Check if the output file exists
if [ -f "$OUTPUT_FILE" ]; then
  # This is the last corpus id processed
  second_word=$(tail -n 1 "$OUTPUT_FILE" | awk '{print $2}')
    if [ ! -z "$second_word" ]; then
        # Find the line number of the first occurrence of this word in the input file
        line_num=$(grep -nm1 "$second_word" "$INPUT_FILE" | cut -d: -f1)
        
        if [ ! -z "$line_num" ]; then
            # Calculate the next line to start processing from
            start_line=$((line_num + 1))
            
            # Find the nearest neighbors based on the SciNCL KNN index
            tail -n +$start_line "$INPUT_FILE" | $JSALTsrc/near_embedding.sh $scincl >> "$OUTPUT_FILE"
        else
            # If the second word from the last line of the output is not found in the input, process the whole file
            cat "$INPUT_FILE" | $JSALTsrc/near_embedding.sh $scincl >> "$OUTPUT_FILE"
        fi
    else
        # If unable to extract the second word, process the whole file
        cat "$INPUT_FILE" | $JSALTsrc/near_embedding.sh $scincl >> "$OUTPUT_FILE"
    fi
else
    # If the output file doesn't exist or is empty, process the whole file
    cat "$INPUT_FILE" | $JSALTsrc/near_embedding.sh $scincl >> "$OUTPUT_FILE"
fi


